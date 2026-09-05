/**
 * An id for one long request, generated before the request is made.
 *
 * WHY THE CLIENT GENERATES IT
 *
 * A request that takes minutes cannot be watched through its own response: the
 * response does not exist until the work has finished, which is after the point
 * at which anybody wanted to know how it was going. So the id is made here, sent
 * with the request, and polled on a separate endpoint while the first request is
 * still open.
 *
 * The upload flow reached this conclusion first and generated its id inline. The
 * policy index build needs exactly the same thing for exactly the same reason,
 * and a second copy of the expression would be a second place for the fallback
 * to be got wrong.
 *
 * HOW STRONG IT HAS TO BE
 *
 * Unique among the operations one server is currently tracking, and no stronger.
 * A collision costs a wrong progress readout — never a wrong document, a wrong
 * index or a wrong decision — because nothing is authorised, addressed or
 * recorded by this value. `crypto.randomUUID` where the browser has it, and a
 * timestamp-and-random string where it does not, which is the case in a
 * non-secure context and in some test environments.
 */
export function newOperationId(prefix = "op"): string {
  return (
    globalThis.crypto?.randomUUID?.() ??
    `${prefix}-${Date.now()}-${Math.random().toString(36).slice(2)}`
  );
}
