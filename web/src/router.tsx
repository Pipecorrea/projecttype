import { createRootRoute, createRoute, createRouter, redirect } from "@tanstack/react-router";
import { Shell } from "@/components/Shell";
import { ManualPage } from "@/routes/manual";

const rootRoute = createRootRoute({ component: Shell });

const indexRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/",
  beforeLoad: () => {
    throw redirect({ to: "/manual" });
  },
});

const manualRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/manual",
  component: ManualPage,
});

const routeTree = rootRoute.addChildren([indexRoute, manualRoute]);

export const router = createRouter({
  routeTree,
  defaultPreload: "intent",
});

declare module "@tanstack/react-router" {
  interface Register {
    router: typeof router;
  }
}
