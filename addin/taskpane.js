/* CAI Guard task pane — polls the local service and renders live status for the open document. */
(function () {
  var docId = "";       // file path / URL of the current Word document
  var timer = null;

  function $(id) { return document.getElementById(id); }

  function setStatus(cls, msg, sub) {
    var s = $("status");
    s.className = "status " + cls;
    $("smsg").textContent = msg;
    $("ssub").textContent = sub || "";
  }

  function render(d) {
    // document name
    $("docname").textContent = d.name || "(unsaved document)";

    if (!d.enrolled) {
      $("hicon").src = "assets/shield-off-80.png";
      setStatus("off", "Not protected", "This document isn’t enrolled in CAI Guard yet. Open the full app to add it.");
      $("grid").style.display = "none";
      $("list-wrap").style.display = "none";
      var cw = $("corrupt"); if (cw) cw.style.display = "none";
      $("ver").textContent = "—";
      return;
    }

    $("ver").textContent = "Baseline v" + (d.version || 1);

    // Corruption takes priority over everything — red shield.
    var corrupt = d.integrity === "corruption";
    var clist = $("clist");
    if (corrupt) {
      $("hicon").src = "assets/shield-red-64.png";
      var alerts = d.alerts || [];
      setStatus("bad", "Corruption detected — " + alerts.length + " problem" + (alerts.length === 1 ? "" : "s"),
                "The file's structure broke on the last save.");
      clist.innerHTML = alerts.map(function (a) {
        var el = '<div class="crow"><div class="cn"></div><div class="cd"></div></div>';
        return el;
      }).join("");
      // fill text safely
      var rows = clist.querySelectorAll(".crow");
      alerts.forEach(function (a, i) {
        if (!rows[i]) return;
        rows[i].querySelector(".cn").textContent = a.name;
        rows[i].querySelector(".cd").textContent = a.detail;
      });
      $("corrupt").style.display = "block";
      $("grid").style.display = "none";
      $("list-wrap").style.display = "none";
      return;
    }
    $("corrupt").style.display = "none";
    $("hicon").src = "assets/shield-64.png";

    var total = d.pending || 0;
    if (total === 0) {
      setStatus("on", "Protected — in sync", "No changes since the approved baseline.");
    } else if ((d.weakened || 0) > 0) {
      setStatus("warn", "Protected — " + d.weakened + " weakened control" + (d.weakened === 1 ? "" : "s"),
                total + " pending change" + (total === 1 ? "" : "s") + " to review.");
    } else {
      setStatus("warn", "Protected — " + total + " pending change" + (total === 1 ? "" : "s"),
                "Review changes against the baseline.");
    }

    $("c-weak").textContent = d.weakened || 0;
    $("c-sem").textContent = d.semantic || 0;
    $("c-struct").textContent = d.structural || 0;
    $("c-cos").textContent = d.cosmetic || 0;
    $("grid").style.display = "grid";

    var list = $("list");
    list.innerHTML = "";
    if (!d.items || d.items.length === 0) {
      list.innerHTML = '<div class="empty">Nothing to review.</div>';
    } else {
      d.items.forEach(function (it) {
        var tag = it.level === "control-weakened"
          ? "Weakened" + (it.weak ? " " + it.weak.from + "→" + it.weak.to : "")
          : it.level;
        // Build with textContent (no innerHTML) so vocab-derived strings can't inject markup.
        var el = document.createElement("div"); el.className = "item";
        var t = document.createElement("span");
        t.className = "tag " + (/^[a-z-]+$/.test(it.level) ? it.level : "");
        t.textContent = tag;
        var body = document.createElement("div"); body.className = "txt";
        body.textContent = it.text || "";
        el.appendChild(t); el.appendChild(body);
        list.appendChild(el);
      });
    }
    $("list-wrap").style.display = "block";
  }

  function poll() {
    fetch("/api/addin/state?doc=" + encodeURIComponent(docId), { cache: "no-store" })
      .then(function (r) { return r.json(); })
      .then(render)
      .catch(function () {
        setStatus("off", "CAI Guard is not running",
                  "Start the CAI Guard app, then reopen this panel.");
        $("grid").style.display = "none";
        $("list-wrap").style.display = "none";
      });
  }

  function begin() {
    // Identify the open document (path or URL). Unsaved docs report empty -> treated as not-enrolled.
    try {
      Office.context.document.getFilePropertiesAsync(function (res) {
        if (res && res.status === Office.AsyncResultStatus.Succeeded && res.value) {
          docId = res.value.url || "";
        }
        poll();
        if (timer) clearInterval(timer);
        timer = setInterval(poll, 4000);
      });
    } catch (e) {
      poll();
      timer = setInterval(poll, 4000);
    }
  }

  if (window.Office) {
    Office.onReady(function () { begin(); });
  } else {
    window.addEventListener("load", begin);
  }
})();
