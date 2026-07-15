"""CLI ``projecttype`` — el enriquecedor como comando (PT-6).

``projecttype enrich --from-store`` cierra el ciclo store→store: lee los
proyectos de CONSULTAS_EBI, clasifica con la cascada L1→L2(→L3 opcional) y
publica ``enr_tipo_proyecto`` de vuelta al store. Sin CSV intermedios.

El camino CSV histórico sigue vivo en ``scripts/classify_cascade.py`` (es útil
para calibración/eval con la submuestra manual); este CLI es el camino de
producción del ecosistema.
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from projecttype.inference_metadata import prompt_version, taxonomy_hash
from projecttype.paths import DEFAULT_L3_CACHE_JSONL, DEFAULT_TAXONOMY
from projecttype.store_publish import enricher_version

app = typer.Typer(
    help="ProjectType — enriquecedor de tipo de proyecto del ecosistema SNI/BIP.",
    no_args_is_help=True,
)


@app.callback()
def _main() -> None:
    """Mantiene el modo subcomando (``projecttype enrich …``)."""


@app.command()
def enrich(
    from_store: Annotated[
        bool,
        typer.Option("--from-store", help="Leer proyectos de CONSULTAS_EBI en el store."),
    ] = False,
    from_selection: Annotated[
        str | None,
        typer.Option(
            "--from-selection",
            help="Clasificar solo los BIP de sel_tipo_proyecto_<id> (SNI-38).",
        ),
    ] = None,
    data_dir: Annotated[
        str | None,
        typer.Option("--data-dir", help="Directorio del store (default: BIP_DATA_DIR)."),
    ] = None,
    limit: Annotated[
        int | None,
        typer.Option("--limit", help="Clasificar solo los primeros N proyectos (piloto)."),
    ] = None,
    incremental: Annotated[
        bool,
        typer.Option(
            "--incremental",
            help="Solo clasificar proyectos sin clasificación vigente con la misma taxonomía/prompt.",
        ),
    ] = False,
    force_selection: Annotated[
        bool,
        typer.Option(
            "--force-selection",
            help="Con --from-selection, reclasificar aunque ya existan en el store.",
        ),
    ] = False,
    enable_l3: Annotated[
        bool,
        typer.Option("--enable-l3", help="Activar el nivel LLM (L3) para el residual."),
    ] = False,
    l3_limit: Annotated[
        int | None,
        typer.Option("--l3-limit", help="Máximo de llamadas LLM en L3."),
    ] = None,
    l3_concurrency: Annotated[
        int | None,
        typer.Option("--l3-concurrency", help="Hilos paralelos L3 (default: LLM_MAX_CONCURRENCY o 5)."),
    ] = None,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help="Clasificar y mostrar el diff del store sin escribir."),
    ] = False,
    allow_rejected: Annotated[
        float,
        typer.Option(
            "--allow-rejected",
            min=0.0,
            max=1.0,
            help="Fracción máxima de filas rechazadas por el gate de publicación (0.0 = estricto).",
        ),
    ] = 0.0,
    out_csv: Annotated[
        Path | None,
        typer.Option("--out", help="Además, guardar los resultados crudos en este CSV."),
    ] = None,
) -> None:
    """Clasifica el tipo de proyecto y publica ``enr_tipo_proyecto`` al store."""
    if from_store and from_selection is not None:
        raise typer.BadParameter("Usa --from-store o --from-selection, no ambos.")
    if not from_store and from_selection is None:
        raise typer.BadParameter(
            "Indica --from-store o --from-selection <id>. "
            "(El camino CSV vive en scripts/classify_cascade.py.)"
        )
    if force_selection and from_selection is None:
        raise typer.BadParameter("--force-selection solo aplica con --from-selection.")
    if incremental and from_selection is not None:
        raise typer.BadParameter("--incremental no aplica con --from-selection (usa el anti-join por defecto).")

    from projecttype.classifier_cascade import ClassifierCascade
    from projecttype.incremental import filter_pending
    from projecttype.pipeline_cascade import classify_cascade_dataframe
    from projecttype.store_input import load_cascade_input_from_store, load_selection_bips
    from projecttype.store_publish import publish_to_store

    tax_hash = taxonomy_hash()
    prompt_ver = prompt_version()
    enricher_ver = enricher_version()
    source_label: str | None = None
    mark_missing = True
    apply_incremental = incremental or from_selection is not None

    if from_selection is not None:
        typer.echo(f"→ Leyendo selección sel_tipo_proyecto_{from_selection}…")
        bips = load_selection_bips(from_selection, data_dir)
        typer.echo(f"  {len(bips)} proyectos en la selección.")
        df = load_cascade_input_from_store(data_dir, bips=bips)
        source_label = f"seleccion:{from_selection}"
        mark_missing = False
    else:
        typer.echo("→ Leyendo proyectos del store (CONSULTAS_EBI)…")
        df = load_cascade_input_from_store(data_dir, limit=limit)
        if incremental:
            mark_missing = False

    if apply_incremental and not force_selection:
        split = filter_pending(
            df,
            data_dir=data_dir,
            tax_hash=tax_hash,
            prompt_ver=prompt_ver,
            enricher_ver=enricher_ver,
        )
        typer.echo(
            f"  a clasificar: {split.pendientes.height} / saltados: {split.saltados.height}"
        )
        if dry_run:
            typer.echo("  (dry-run: no se clasificó ni publicó)")
            return
        df = split.pendientes
    elif dry_run and incremental:
        typer.echo(f"  {df.height} proyectos a clasificar.")
        typer.echo("  (dry-run: no se clasificó ni publicó)")
        return

    if df.height == 0:
        typer.echo("  Nada pendiente de clasificar.")
        return

    typer.echo(f"  {df.height} proyectos a clasificar.")

    cascade = ClassifierCascade.from_yaml(DEFAULT_TAXONOMY, enable_l3=enable_l3)
    typer.echo(f"→ Clasificando (L1→L2{'→L3' if enable_l3 else ''})…")
    result = classify_cascade_dataframe(
        df,
        cascade,
        l3_limit=l3_limit,
        l3_concurrency=l3_concurrency,
        l3_cache_path=DEFAULT_L3_CACHE_JSONL if enable_l3 else None,
    )

    if out_csv is not None:
        out_csv.parent.mkdir(parents=True, exist_ok=True)
        result.write_csv(out_csv)
        typer.echo(f"  Resultados crudos → {out_csv}")

    if limit is not None and not dry_run and not incremental and from_selection is None:
        typer.confirm(
            f"⚠ Vas a publicar solo {df.height} proyectos: el resto de "
            "enr_tipo_proyecto quedará marcado como ausente del último snapshot. "
            "¿Continuar?",
            abort=True,
        )

    if dry_run:
        typer.echo("  (dry-run: no se escribió nada)")
        return

    typer.echo("→ Publicando enr_tipo_proyecto al store…")
    from projecttype.store_gate import StoreGateRejectedError, formatear_resumen_gate

    try:
        diag = publish_to_store(
            result,
            data_dir=data_dir,
            dry_run=False,
            mark_missing=mark_missing,
            source_label=source_label,
            allow_rejected_pct=allow_rejected,
        )
    except StoreGateRejectedError as exc:
        typer.echo(formatear_resumen_gate(exc.resultado), err=True)
        raise typer.Exit(code=1) from exc
    typer.echo(diag.summary())


@app.command(name="verify-llm")
def verify_llm(
    provider: Annotated[
        str | None,
        typer.Option("--provider", help="Override del proveedor (default: LLM_PROVIDER o gemini)."),
    ] = None,
    model: Annotated[
        str | None,
        typer.Option("--model", help="Override del modelo (default: resuelto del proveedor)."),
    ] = None,
) -> None:
    """Smoke del proveedor LLM configurado: credenciales + chat + salida estructurada.

    Verifica el mismo camino que usa L3 en producción (PT-25): primero un chat
    simple (conectividad/credenciales), luego un ``structured_output`` real con
    ``L3ResponseModel`` (el schema exacto que fuerza el backend en cada fila L3).
    Falla temprano con mensaje accionable en vez de descubrir credenciales/ADC
    vencidas a mitad de una corrida de ``enrich --enable-l3``.
    """
    import asyncio

    from sni_commons.llm import Message

    from projecttype.l3_schema import L3ResponseModel
    from projecttype.llm.provider import build_provider, check_provider_available, describe_provider

    typer.echo(f"Proveedor: {describe_provider(provider)}")
    try:
        check_provider_available(provider)
    except RuntimeError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    llm_provider = build_provider(provider, model=model)

    try:
        chat_resp = asyncio.run(
            llm_provider.chat([Message(role="user", content="Responde solo: OK")], max_tokens=32)
        )
        typer.echo(f"[1/2] Chat simple → {chat_resp.text!r}")
    except Exception as exc:  # noqa: BLE001 — cualquier fallo del backend es diagnóstico aquí
        typer.echo(f"[1/2] Falló la llamada simple: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    try:
        structured_resp = asyncio.run(
            llm_provider.structured_output(
                [
                    Message(
                        role="system",
                        content="Sos un clasificador. Devuelve tipo_id=null y confianza=0.0.",
                    ),
                    Message(role="user", content="Smoke test, sin proyecto real."),
                ],
                L3ResponseModel,
            )
        )
        typer.echo(f"[2/2] Salida estructurada → {structured_resp.data.model_dump()}")
    except Exception as exc:  # noqa: BLE001
        typer.echo(f"[2/2] Falló la llamada estructurada: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    typer.echo("\nOK — el proveedor está listo para L3.")


@app.command()
def serve(
    host: Annotated[
        str,
        typer.Option("--host", help="Host de escucha (default 127.0.0.1)."),
    ] = "127.0.0.1",
    port: Annotated[
        int,
        typer.Option("--port", help="Puerto (default 8788 o PROJECTTYPE_UI_PORT)."),
    ] = 0,
    data_dir: Annotated[
        Path | None,
        typer.Option("--data-dir", help="Store canónico (default BIP_DATA_DIR)."),
    ] = None,
    reload: Annotated[
        bool,
        typer.Option("--reload", help="Autoreload (solo desarrollo)."),
    ] = False,
) -> None:
    """Levanta la UI HITL (revisión + clasificación manual + editor de prompts).

    Read-only sobre el store (D-13): los veredictos van a un JSONL aparte; el
    publish al store solo por el loop de salida (PT-21).
    """
    import os

    import uvicorn

    from projecttype.api.main import DEFAULT_PORT, create_app

    resolved_port = port or int(os.environ.get("PROJECTTYPE_UI_PORT", str(DEFAULT_PORT)))
    application = create_app(data_dir=data_dir, load_snapshot=True)
    summary = application.state.review_store.summary()
    typer.echo(
        f"→ Snapshot: {summary.total_clasificados} clasificados "
        f"({summary.revisados} revisados) · taxonomy_hash={summary.taxonomy_hash}"
    )
    typer.echo(f"→ UI HITL en http://{host}:{resolved_port}")
    uvicorn.run(application, host=host, port=resolved_port, reload=reload)


if __name__ == "__main__":  # pragma: no cover
    app()
