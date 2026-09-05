/**
 * Who may see Integration, and when.
 *
 * Two independent conditions have to hold before the page appears: the caller
 * must be an administrator, and the deployment must issue its own subscription
 * keys. They are separate because they answer different questions — one is
 * about the person, the other about where the software is running — and either
 * one alone is not enough.
 *
 * The role half lives in the surface map and is tested here. The deployment
 * half is a runtime probe folded into `hiddenNavIds` in `App.tsx`, which feeds
 * both the rendered menu and the navigation guard from one expression, so a
 * hidden page cannot be reached by typing its route. The server refuses the
 * endpoints regardless of either, which is the control that actually protects
 * the keys — the menu is a courtesy.
 */
import { describe, expect, it } from "vitest";
import { canAccessPage, surfaceAccess } from "./rbac";

describe("Integration is an administrative surface", () => {
  it("is visible to an administrator", () => {
    expect(canAccessPage("admin", "integration")).toBe(true);
  });

  it.each(["viewer", "policy_author"])("is hidden from %s", (role) => {
    expect(canAccessPage(role, "integration")).toBe(false);
  });

  it("is hidden from an unknown role by the closed default", () => {
    expect(canAccessPage("auditor-we-never-defined", "integration")).toBe(false);
    expect(canAccessPage(undefined, "integration")).toBe(false);
  });

  it("resolves to a definite decision for every role, not an accidental absence", () => {
    // The control for the three refusals above. `surfaceAccess` returns a
    // closed default for anything it does not recognise, so "hidden" alone
    // cannot distinguish "deliberately denied" from "never added to the map".
    for (const role of ["viewer", "policy_author", "admin"]) {
      const access = surfaceAccess(role, "integration");
      expect(access, role).toHaveProperty("visible");
      expect(access.blockedReason, role).not.toBe(
        surfaceAccess(role, "a-surface-that-does-not-exist").blockedReason,
      );
    }
  });

  it("does not make an administrator lose anything else", () => {
    // Guards against a map edit that granted Integration by overwriting a
    // neighbouring entry.
    for (const id of ["dashboard", "projects", "document-inbox", "evaluate"]) {
      expect(canAccessPage("admin", id), id).toBe(true);
    }
  });
});
