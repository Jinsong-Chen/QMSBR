/* QMSBR R lab workspace. Original code: MIT; see LICENSE.
   The pinned Quarto Live adapter supplies its existing WebR instance. */
(function () {
  "use strict";
  // Runs on every page. The chapter pages carry live code cells but no
  // workspace panel, so the runtime notice cannot depend on one. Each page
  // names its own fixed code and output through window.qmsbrSuppliedOutput.
  const unavailable = () => {
    document.body.classList.add("qmsbr-engine-failed");
    const target = window.qmsbrSuppliedOutput || "#supplied-output";
    document.querySelectorAll(".exercise-cell").forEach((cell) => {
      cell.classList.add("qmsbr-runtime-unavailable");
      const message = document.createElement("p");
      message.className = "qmsbr-fallback";
      message.append("R could not start for this activity. ");
      const link = document.createElement("a");
      link.href = target;
      link.textContent = "Continue with the supplied code and output.";
      message.append(link);
      cell.prepend(message);
    });
  };
  window.qmsbrRuntime = {
    // A chapter page hands over the same webR promise its live cells use.
    watch(webRPromise) {
      Promise.resolve(webRPromise).then(undefined, unavailable);
      return "";
    }
  };

  const root = document.getElementById("r-workspace");
  if (!root) return;
  const $ = (selector) => root.querySelector(selector);
  const status = $(".qmsbr-status");
  const code = $(".qmsbr-code");
  const output = $(".qmsbr-output");
  const notes = $(".qmsbr-notes");
  const csvInput = $('[data-file="csv"]');
  const runButton = $('[data-action="run"]');
  const runAllButton = $('[data-action="run-all"]');
  const clearButton = $('[data-action="clear"]');
  const imported = new Set();
  let engine, environment, attached = false, busy = false;
  let lastCode = "", lastOutput = "", lastInputs = [];
  let history = [], lastHistory = "";
  const setStatus = (message) => { status.textContent = message; };
  const setBusy = (value) => {
    busy = value;
    runButton.disabled = runAllButton.disabled = clearButton.disabled = csvInput.disabled = value || !engine;
  };
  function save(blob, name) {
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = name;
    a.click();
    setTimeout(() => URL.revokeObjectURL(url), 10000);
  }
  function saveText(text, name) {
    save(new Blob([text], { type: "text/plain;charset=utf-8" }), name);
  }
  $('[data-action="save-code"]').addEventListener("click", () => {
    const inputs = [...imported].map((name) => `# Input CSV: ${name}`).join("\n");
    saveText(`# R work from QMSBR R lab\n# Keep the input files with this script.\n${inputs}\n\n${code.value}\n`, "my-analysis.R");
    setStatus("Saved the current editor text, including any edits you have not run.");
  });
  $('[data-action="save-results"]').addEventListener("click", () => {
    const changed = code.value !== lastCode;
    const text = `QMSBR R lab\nPage: ${location.href}\n` +
      `Input files at last run: ${lastInputs.join(", ") || "none imported"}\n\n` +
      `CODE USED FOR THE MOST RECENT OUTPUT\n${lastCode || "No completed run yet."}\n\n` +
      `COMMANDS SUBMITTED FOR THIS OUTPUT (in order)\n${lastHistory || "No completed run yet."}\n\n` +
      `OUTPUT\n${lastOutput || "No completed run yet."}\n\n` +
      `INTERPRETATION\n${notes.value}\n` +
      (changed ? `\nCURRENT EDITOR DRAFT (different from the code above)\n${code.value}\n` : "");
    saveText(text, "my-results.txt");
    setStatus("Saved the output, the code that produced it, and your interpretation. Save plots separately using their buttons.");
  });
  $('[data-file="script"]').addEventListener("change", async (event) => {
    const file = event.target.files[0];
    if (!file) return;
    if (file.size > 1024 * 1024) {
      setStatus("Choose an R script smaller than 1 MB.");
      event.target.value = "";
      return;
    }
    try {
      code.value = await file.text();
      setStatus(`Opened ${file.name}. Open any required CSVs, then run the complete script.`);
    } catch (error) { setStatus(`Could not open the script: ${error.message}`); }
    event.target.value = "";
  });
  async function conditionText(item) {
    if (typeof item.data === "string") return item.data;
    try {
      return await engine.evalRString("conditionMessage(condition)", { env: { condition: item.data } });
    } catch (_) { return "R reported a condition. Check the code and data."; }
  }
  async function capture(source, env, graphics) {
    const shelter = await new engine.Shelter();
    try {
      const result = await shelter.captureR(source, {
        env, withAutoprint: true,
        captureGraphics: graphics ? { width: 720, height: 440 } : false
      });
      const lines = [];
      let error = false;
      for (const item of result.output) {
        if (item.type === "error") error = true;
        const prefix = ["error", "warning", "message"].includes(item.type) ? `${item.type}: ` : "";
        lines.push(prefix + await conditionText(item));
      }
      return { text: lines.join("\n"), error, images: result.images || [] };
    } finally { await shelter.purge(); }
  }
  csvInput.addEventListener("change", async (event) => {
    const file = event.target.files[0];
    if (!file || busy || !engine) return;
    // Only basenames become VFS paths: imported files cannot replace data/... resources.
    if (!/^[A-Za-z0-9][A-Za-z0-9_. -]*\.csv$/i.test(file.name)) {
      setStatus("Use a CSV filename containing letters, numbers, spaces, dots, underscores, or hyphens.");
      event.target.value = "";
      return;
    }
    if (!file.size || file.size > 5 * 1024 * 1024) {
      setStatus("Choose a nonempty CSV smaller than 5 MB.");
      event.target.value = "";
      return;
    }
    setBusy(true);
    try {
      const bytes = new Uint8Array(await file.arrayBuffer());
      if (bytes.includes(0)) throw new Error("This appears to be a binary file. Export a plain CSV first.");
      // Validate in a separate file/environment before replacing any previously imported file.
      const temporary = ".qmsbr-import-check.csv";
      await engine.FS.writeFile(temporary, bytes);
      const preview = await capture(`
        preview <- read.csv(".qmsbr-import-check.csv", check.names = FALSE)
        if (nrow(preview) == 0 || ncol(preview) < 2) stop("Use a CSV with a header, at least two columns, and at least one data row.")
        if (any(names(preview) == "") || anyDuplicated(names(preview))) stop("Each column needs a distinct, nonempty name.")
        cat(nrow(preview), "rows and", ncol(preview), "columns\\n\\n")
        print(head(preview, 6))
        cat("\\nMissing values by column:\\n")
        print(colSums(is.na(preview)))
      `, {}, false);
      await engine.FS.unlink(temporary);
      if (preview.error) throw new Error(preview.text);
      await engine.FS.writeFile(file.name, bytes);
      imported.add(file.name);
      $(".qmsbr-preview").hidden = false;
      $(".qmsbr-preview").textContent = `${file.name}\n${preview.text}`;
      setStatus(`Opened ${file.name}. Read it with read.csv(${JSON.stringify(file.name)}) in your code. No file was sent to a server.`);
    } catch (error) { setStatus(`CSV not opened: ${error.message}`); }
    finally { event.target.value = ""; setBusy(false); }
  });
  async function runCode(full) {
    if (busy || !engine) return;
    setBusy(true);
    setStatus(full ? "Running the whole script…" : "Running selected code or the current complete command…");
    let currentCode = "";
    const currentInputs = [...imported];
    try {
      const part = full ? { code: code.value } : await window.qmsbrCommands.command(
        engine, code.value, code.selectionStart, code.selectionEnd);
      currentCode = part.code;
      if (!currentCode.trim()) { setStatus("Place the cursor on a command, or select code."); return; }
      history.push(currentCode);
      lastHistory = history.join("\n\n");
      const result = await capture(currentCode, environment, true);
      lastCode = currentCode;
      lastOutput = result.text || "Completed without printed output.";
      lastInputs = currentInputs;
      if (!full && code.selectionStart === code.selectionEnd) {
        code.setSelectionRange(part.next, part.next);
      }
      output.textContent = lastOutput;
      $(".qmsbr-plots").replaceChildren();
      result.images.forEach((bitmap, index) => {
        const figure = document.createElement("figure");
        const canvas = document.createElement("canvas");
        canvas.width = bitmap.width;
        canvas.height = bitmap.height;
        canvas.setAttribute("role", "img");
        canvas.setAttribute("aria-label", `Plot ${index + 1} from your R code`);
        canvas.getContext("2d").drawImage(bitmap, 0, 0);
        bitmap.close();
        const button = document.createElement("button");
        button.type = "button";
        button.textContent = `Save plot ${index + 1}`;
        button.addEventListener("click", () => canvas.toBlob((blob) => save(blob, `my-plot-${index + 1}.png`)));
        figure.append(canvas, button);
        $(".qmsbr-plots").append(figure);
      });
      setStatus(result.error ? "R reported an error. Read the message, edit the code, and run it again." : "Run complete. Check the output and write your interpretation.");
    } catch (error) {
      output.textContent = `Error: ${error.message}`;
      lastCode = currentCode;
      lastOutput = output.textContent;
      lastInputs = currentInputs;
      setStatus("The calculation did not finish. Check the error; you can still save your code.");
    } finally { setBusy(false); }
  }
  runButton.addEventListener("click", () => runCode(false));
  runAllButton.addEventListener("click", () => runCode(true));
  code.addEventListener("keydown", (event) => {
    if (event.key === "Enter" && (event.ctrlKey || event.metaKey)) {
      event.preventDefault();
      runCode(false);
    }
  });
  clearButton.addEventListener("click", async () => {
    if (busy || !engine) return;
    setBusy(true);
    try {
      await engine.evalRVoid("rm(list = ls(all.names = TRUE))", { env: environment });
      history = [];
      setStatus("R objects cleared. Your code, files, and displayed results remain. Rerun the full script for new results.");
    } catch (error) { setStatus(error.message); }
    finally { setBusy(false); }
  });
  // This message also stays useful when the extension itself cannot load.
  const loadingTimer = setTimeout(() => {
    if (!engine) setStatus("R is taking longer to load. The supplied static output is available under Fixed code and output. You can save code for desktop R, or reload to retry.");
  }, 25000);
  window.qmsbrWorkspace = {
    async attach(webRPromise) {
      if (attached) return "";
      attached = true;
      try {
        engine = await webRPromise;
        environment = await engine.evalR("new.env(parent = globalenv())");
        clearTimeout(loadingTimer);
        setBusy(false);
        setStatus("R is ready. Run the starting code, paste your course code, or open a CSV.");
      } catch (error) {
        clearTimeout(loadingTimer);
        engine = undefined;
        setBusy(false);
        unavailable();
        setStatus("R could not start. Use the supplied code and output under Fixed code and output, save code for desktop R, or reload to retry.");
      }
      return "";
    }
  };
})();

