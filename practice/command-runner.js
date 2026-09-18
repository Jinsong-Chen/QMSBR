/* QMSBR selection/current-command controls for the pinned Quarto Live editor.
   Original code: MIT; see LICENSE. Keep vendor runtime bundles unchanged. */
(function () {
  "use strict";

  // Ask R's parser for a complete expression; never execute code to find its end.
  // Parsing successive complete groups also allows a valid command before a
  // later syntax error to run. Explicit selections are submitted exactly as-is.
  async function command(engine, source, from, to) {
    if (from !== to) return { code: source.slice(from, to), from, to };
    const prefix = source.slice(0, from).split("\n");
    const line = prefix.length;
    const encoder = new TextEncoder();
    const column = encoder.encode(prefix[prefix.length - 1]).length + 1;
    const shelter = await new engine.Shelter();
    let positions;
    try {
    const range = await shelter.evalR(`{
      lines <- strsplit(source, "\\n", fixed = TRUE)[[1]]
      first <- 1L
      found <- integer()
      complete <- tryCatch(parse(text = source, keep.source = TRUE), error = identity)
      if (!inherits(complete, "error") && length(complete)) {
        refs <- attr(complete, "srcref")
        chosen <- refs[[length(refs)]]
        for (ref in refs) {
          if (ref[3] > line || (ref[3] == line && ref[4] >= column)) {
            chosen <- ref
            break
          }
        }
        found <- chosen[c(1, 2, 3, 4)]
      }
      if (!length(found)) {
      for (last in seq_along(lines)) {
        part <- paste(lines[first:last], collapse = "\\n")
        parsed <- tryCatch(parse(text = part, keep.source = TRUE), error = identity)
        if (inherits(parsed, "error")) {
          if (last >= line && !grepl("unexpected end of input|INCOMPLETE_STRING", conditionMessage(parsed)))
            stop(conditionMessage(parsed), call. = FALSE)
          next
        }
        if (!length(parsed)) next
        refs <- attr(parsed, "srcref")
        if (last >= line) {
          for (ref in refs) {
            end_line <- first + ref[3] - 1L
            if (end_line > line || (end_line == line && ref[4] >= column)) {
              found <- c(first + ref[1] - 1L, ref[2], end_line, ref[4])
              break
            }
          }
          if (!length(found)) {
            ref <- refs[[length(refs)]]
            found <- c(first + ref[1] - 1L, ref[2], first + ref[3] - 1L, ref[4])
          }
          break
        }
        first <- last + 1L
      }
      if (!length(found) && first <= length(lines)) {
        parse(text = paste(lines[first:length(lines)], collapse = "\\n"))
      }
      }
      found
    }`, { env: { source, line, column } });
    positions = await range.toArray();
    } finally { await shelter.purge(); }
    if (!positions.length) return { code: "", from, to };
    const lines = source.split("\n");
    const offset = (row, col) => lines.slice(0, row - 1).reduce((n, s) => n + s.length + 1, 0) +
      new TextDecoder().decode(encoder.encode(lines[row - 1]).slice(0, col)).length;
    const start = offset(positions[0], positions[1] - 1);
    const end = offset(positions[2], positions[3]);
    const skip = source.slice(end).match(/^[;\s]*/)[0].length;
    return { code: source.slice(start, end), from: start, to: end, next: end + skip };
  }

  function mount(editor, promise) {
    const container = editor.container;
    const run = container.querySelector('[aria-label="Run Code"]');
    if (!run) return;
    const all = document.createElement("button");
    all.type = "button";
    all.className = "btn btn-outline-primary btn-sm";
    all.textContent = "Run All";
    all.disabled = true;
    run.after(all);
    run.title = "Run selected code, or the complete command at the cursor";
    const status = document.createElement("div");
    status.className = "qmsbr-command-status small px-3 pb-2";
    status.setAttribute("role", "status");
    status.textContent = "Run Code: selection or current command. Run All: whole block.";
    container.append(status);
    let engine, busy = false;
    const commit = (code) => container.dispatchEvent(new CustomEvent("input", {
      detail: { commit: true, code, qmsbr: true }
    }));
    async function execute(full) {
      if (!engine || busy || run.classList.contains("disabled")) return;
      busy = true;
      try {
        const source = editor.view.state.doc.toString();
        const selection = editor.view.state.selection.main;
        const part = full ? { code: source } : await command(engine, source, selection.from, selection.to);
        if (!part.code.trim()) { status.textContent = "Place the cursor on a command, or select code."; return; }
        commit(part.code);
        status.textContent = full ? "Submitted the whole block." : "Submitted selected code or the current complete command.";
        // Advance only a cursor run; a selection stays selected for easy reruns.
        if (!full && selection.empty) {
          editor.view.dispatch({ selection: { anchor: part.next } });
        }
      } catch (error) { status.textContent = `Code was not run: ${error.message}`; }
      finally { busy = false; }
    }
    // Capture the vendor's input event before its full-document onInput handler.
    container.addEventListener("input", (event) => {
      if (!event.detail?.commit || event.detail.qmsbr) return;
      event.stopImmediatePropagation();
      execute(false);
    }, true);
    container.addEventListener("keydown", (event) => {
      if (event.key === "Enter" && (event.ctrlKey || event.metaKey)) {
        event.preventDefault();
        event.stopImmediatePropagation();
        execute(false);
      }
    }, true);
    run.onclick = () => execute(false);
    run.onkeydown = null;
    run.addEventListener("keydown", (event) => {
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        execute(false);
      }
    });
    all.addEventListener("click", () => execute(true));
    const reset = container.querySelector('[aria-label="Start Over"]');
    if (reset) {
      reset.onclick = reset.onkeydown = null;
      const startOver = async () => {
        if (!engine || busy || run.classList.contains("disabled")) return;
        busy = true;
        try {
          const manager = window._exercise_ojs_runtime.WebREnvironment.instance(engine);
          await manager.destroy(`${editor.options.envir}-result`);
          await manager.destroy(`${editor.options.envir}-prep`);
          editor.view.dispatch({ changes: { from: 0, to: editor.view.state.doc.length, insert: editor.initialCode }, selection: { anchor: 0 } });
          commit(null);
          status.textContent = "Starting code restored and this block's R objects cleared. Use Run All or run commands in order.";
        } finally { busy = false; }
      };
      reset.addEventListener("click", startOver);
      reset.addEventListener("keydown", (event) => {
        if (event.key === "Enter" || event.key === " ") { event.preventDefault(); startOver(); }
      });
    }
    promise.then((value) => { engine = value; all.disabled = false; }).catch(() => {});
  }
  window.qmsbrCommands = { command, mount };
})();
