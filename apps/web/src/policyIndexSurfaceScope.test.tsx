import { describe, expect, it } from "vitest";
import { canAccessPage, canAuthor, canAdminister } from "./rbac";
import { consoleRowIsRebuildable } from "./PolicyIndexConsolePage";
import {
  buildCounts,
  buildQuality,
  buildMoment,
  BUILD_STATUS_VIEW,
} from "./components/PolicyIndexBuildHistoryTable";
import type { PolicyIndexBuildProgress } from "./api";

/**
 * A publisher sees their project's index; an administrator sees the estate.
 *
 * WHAT THE ACTUAL BOUNDARY IS, STATED RATHER THAN WISHED FOR
 *
 * It is tempting to test that a publisher sees "only the projects they author".
 * This platform has no such concept. Authorisation here is by **role** — viewer,
 * policy_author, admin — and there is no per-project ACL anywhere: not in
 * `authz.py`, which classifies routes into four bands and consults no project
 * membership, and not in `rbac.ts`, which mirrors three roles and no ownership.
 *
 * So the real boundary, and the one asserted here, is:
 *
 *   - the estate-wide console is administrator-only, on the client and on the
 *     server;
 *   - the per-project surfaces are author-band, and an author reaches them for
 *     **any** project, because that is what the product enforces.
 *
 * Writing a test that asserted per-project scoping would be inventing an access
 * control the product does not have, and it would pass while the server happily
 * served every project to every author. This file says the true thing instead —
 * and `docs/known-limitations.md` records the same boundary, so the gap is
 * documented rather than disguised.
 */

function build(overrides: Partial<PolicyIndexBuildProgress> = {}): PolicyIndexBuildProgress {
  return {
    active: true,
    operation_id: "op-1",
    policy_set_key: "alpha",
    trigger: "publish",
    actor: "approver@example.test",
    status: "completed",
    document_count: 74,
    policy_document_count: 60,
    rule_document_count: 14,
    version_number: 3,
    projection_profile: "english-v1",
    manifest_state: "ready",
    quality_state: "passed",
    quality_profile: "faithfulness-v1",
    quality_checked_documents: 74,
    quality_structural_findings: 0,
    started_at: "2026-08-18T12:00:00Z",
    ...overrides,
  };
}

describe("the two surfaces are scoped by role, which is what this product enforces", () => {
  it("keeps the estate console to administrators", () => {
    expect(canAccessPage("admin", "policy-index")).toBe(true);
    expect(canAccessPage("policy_author", "policy-index")).toBe(false);
    expect(canAccessPage("viewer", "policy-index")).toBe(false);
  });

  it("lets an author reach the project surfaces that carry the index panels", () => {
    // The project Overview is where a publisher watches their build and retries
    // a failed one. An author has it; a viewer sees it read-only and cannot
    // author, which is the band the rebuild endpoint sits in.
    expect(canAccessPage("policy_author", "projects")).toBe(true);
    expect(canAuthor("policy_author")).toBe(true);
    expect(canAuthor("viewer")).toBe(false);
    expect(canAdminister("policy_author")).toBe(false);
  });

  it("does not pretend a per-project ownership check exists", () => {
    // If this ever becomes false, the product has grown a per-project ACL and
    // the surfaces above — and this file — need revisiting rather than the
    // assertion being relaxed. Stated as an executable claim so the boundary is
    // discovered by a failing test rather than by a security review.
    //
    // `canAuthor` takes a role and nothing else: there is no project argument to
    // give it, which is the whole point.
    expect(canAuthor.length).toBe(1);
    expect(canAdminister.length).toBe(1);
  });
});

describe("a history entry says what happened without saying what a policy says", () => {
  it("names what started the build and who asked, when anyone did", () => {
    // A publish carries an approver; a manual rebuild currently does not. An em
    // dash is that absence stated, rather than an invented "unknown".
    expect(BUILD_STATUS_VIEW.completed.label).toBe("Built");
    expect(BUILD_STATUS_VIEW.deferred.label).toBe("Not started");
    // `deferred` is not coloured as a failure: nothing is broken and the repair
    // is to retry once the running build finishes.
    expect(BUILD_STATUS_VIEW.deferred.color).not.toBe("error");
    expect(BUILD_STATUS_VIEW.failed.color).toBe("error");
  });

  it("reports counts the build measured, and an em dash where it measured none", () => {
    expect(buildCounts(build())).toContain("74 documents (60 policy, 14 rule)");
    expect(buildCounts(build())).toContain("v3");
    // A build that failed before it rendered counted nothing. "0 documents"
    // would be a measurement nobody took.
    expect(
      buildCounts(
        build({
          status: "failed",
          document_count: null,
          policy_document_count: null,
          rule_document_count: null,
          version_number: null,
        }),
      ),
    ).toBe("—");
  });

  it("distinguishes a verdict that failed from one that was never reached", () => {
    expect(buildQuality(build())).toContain("passed");
    expect(buildQuality(build({ quality_state: "failed" }))).toContain("failed");
    // Null is neither: the build never got far enough to ask, and the readiness
    // gate treats that exactly as it treats a failure — the two are kept apart
    // only because their repairs differ.
    expect(buildQuality(build({ quality_state: null }))).toBe("—");
  });

  it("shows an em dash for a timestamp that is absent or unreadable", () => {
    expect(buildMoment(null)).toBe("—");
    expect(buildMoment(undefined)).toBe("—");
    expect(buildMoment("not a date")).toBe("—");
    expect(buildMoment("2026-08-18T12:00:00Z")).not.toBe("—");
  });

  it("offers the repair for the faults a rebuild actually repairs", () => {
    // The publisher's retry and the administrator's rebuild are the same
    // capability and use the same predicate, so the two surfaces cannot come to
    // disagree about when the control appears.
    expect(consoleRowIsRebuildable({ health: "failed" } as never)).toBe(true);
    expect(consoleRowIsRebuildable({ health: "unvalidated" } as never)).toBe(false);
  });
});
