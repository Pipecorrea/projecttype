"""CLI ``proyecttype`` — el enriquecedor como comando (PT-6).

``proyecttype enrich --from-store`` cierra el ciclo store→store: lee los
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

from proyecttype.paths import DEFAULT_L3_CACHE_JSONL, DEFAULT_TAXONOMY

app = typer.Typer(
    help="ProyectType — enriquecedor de tipo de proyecto del ecosistema SNI/BIP.",
    no_args_is_help=True,
)


@app.callback()
def _main() -> None:
    """Mantiene el modo subcomando (``proyecttype enrich …``)."""


@app.command()
def enrich(
    from_store: Annotated[
        bool,
        typer.Option("--from-store", help="Leer proyectos de CONSULTAS_EBI en el store."),
    ] = False,
    data_dir: Annotated[
        str | None,
        typer.Option("--data-dir", help="Directorio del store (default: BIP_DATA_DIR)."),
    ] = None,
    limit: Annotated[
        int | None,
        typer.Option("--limit", help="Clasificar solo los primeros N proyectos (piloto)."),
    ] = None,
    enable_l3: Annotated[
        bool,
        typer.Option("--enable-l3", help="Activar el nivel LLM (L3) para el residual."),
    ] = False,
    l3_limit: Annotated[
        int | None,
        typer.Option("--l3-limit", help="Máximo de llamadas LLM en L3."),
    ] = None,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help="Clasificar y mostrar el diff del store sin escribir."),
    ] = False,
    out_csv: Annotated[
        Path | None,
        typer.Option("--out", help="Además, guardar los resultados crudos en este CSV."),
    ] = None,
) -> None:
    """Clasifica el tipo de proyecto y publica ``enr_tipo_proyecto`` al store."""
    if not from_store:
        raise typer.BadParameter(
            "Este comando opera contra el store: usa --from-store. "
            "(El camino CSV vive en scripts/classify_cascade.py.)"
        )

    from proyecttype.classifier_cascade import ClassifierCascade
    from proyecttype.pipeline_cascade import classify_cascade_dataframe
    from proyecttype.store_input import load_cascade_input_from_store
    from proyecttype.store_publish import publish_to_store

    typer.echo("→ Leyendo proyectos del store (CONSULTAS_EBI)…")
    df = load_cascade_input_from_store(data_dir, limit=limit)
    typer.echo(f"  {df.height} proyectos a clasificar.")

    cascade = ClassifierCascade.from_yaml(DEFAULT_TAXONOMY, enable_l3=enable_l3)
    typer.echo(f"→ Clasificando (L1→L2{'→L3' if enable_l3 else ''})…")
    result = classify_cascade_dataframe(
        df,
        cascade,
        l3_limit=l3_limit,
        l3_cache_path=DEFAULT_L3_CACHE_JSONL if enable_l3 else None,
    )

    if out_csv is not None:
        out_csv.parent.mkdir(parents=True, exist_ok=True)
        result.write_csv(out_csv)
        typer.echo(f"  Resultados crudos → {out_csv}")

    if limit is not None and not dry_run:
        # Un publish PARCIAL marca _present_in_latest=false en todo lo que no
        # vino en este lote → los consumidores (p. ej. SNI --filter
        # tipo_proyecto=…) dejarían de ver lo ya clasificado. Los pilotos van
        # con --dry-run; el publish real es de corrida completa.
        typer.confirm(
            f"⚠ Vas a publicar solo {df.height} proyectos: el resto de "
            "enr_tipo_proyecto quedará marcado como ausente del último snapshot. "
            "¿Continuar?",
            abort=True,
        )

    typer.echo("→ Publicando enr_tipo_proyecto al store…")
    diag = publish_to_store(result, data_dir=data_dir, dry_run=dry_run)
    typer.echo(diag.summary())
    if dry_run:
        typer.echo("  (dry-run: no se escribió nada)")


if __name__ == "__main__":  # pragma: no cover
    app()
