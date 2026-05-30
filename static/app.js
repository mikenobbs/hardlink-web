(function () {
  function qs(sel, root=document){ return root.querySelector(sel); }
  function qsa(sel, root=document){ return Array.from(root.querySelectorAll(sel)); }

  const hamburger = qs("#menuHamburger");
  const dropdown = qs("#menuDropdown");
  if (hamburger && dropdown) {
    hamburger.addEventListener("click", () => {
      dropdown.classList.toggle("is-open");
    });
    
    document.addEventListener("click", (e) => {
      if (!hamburger.contains(e.target) && !dropdown.contains(e.target)) {
        dropdown.classList.remove("is-open");
      }
    });
    
    const form = qs(".settings-form", dropdown);
    if (form) {
      form.addEventListener("submit", () => {
        dropdown.classList.remove("is-open");
      });
    }
  }

  qsa("[data-collapse-toggle]").forEach(btn => {
    const targetSel = btn.getAttribute("data-collapse-toggle");
    const target = qs(targetSel);
    if (!target) return;

    target.classList.add("is-collapsed");
    btn.setAttribute("aria-expanded", "false");

    btn.addEventListener("click", () => {
      const collapsed = target.classList.toggle("is-collapsed");
      btn.setAttribute("aria-expanded", collapsed ? "false" : "true");
      const chev = qs(".chev", btn);
      if (chev) chev.textContent = collapsed ? "▾" : "▴";
    });
  });

  if (qs("#folderSearch")) {
    const folderSearch = qs("#folderSearch");
    const folderList = qs("#folderList");

    folderSearch.addEventListener("input", function() {
      const searchTerm = this.value.toLowerCase().trim();
      const folders = folderList.querySelectorAll("[data-folder-name]");
      
      folders.forEach(folder => {
        const name = folder.getAttribute("data-folder-name").toLowerCase();
        folder.style.display = (searchTerm === "" || name.includes(searchTerm)) ? "" : "none";
      });
    });
  }

  const form = qs("#hardlinkForm");
  if (!form) return;

  const filesPanel = form.closest(".panel-files") || form; // works either way

  const checks = qsa("[data-filecheck]", form);
  const selectAllBtn = qs("#selectAllBtn", form);
  const selectNoneBtn = qs("#selectNoneBtn", form);
  const selectedCount = qs("#selectedCount", form);

  function updateCount() {
    const n = checks.filter(c => c.checked).length;
    if (selectedCount) selectedCount.textContent = String(n);
  }

  function setRenameVisibility(blockEl, checked) {
    const wrap = qs("[data-renamewrap]", blockEl);
    const input = qs("[data-renameinput]", blockEl);
    if (!wrap) return;
    wrap.style.display = checked ? "block" : "none";
    if (!checked && input) input.value = "";
  }

  function updateRenameState() {
    if (!filesPanel) return;
    const anyVisibleRename = qsa("[data-renamewrap]", form).some(w => w.style.display !== "none");
    filesPanel.classList.toggle("has-rename", anyVisibleRename);
  }

  checks.forEach(c => {
    const block = c.closest("[data-fileblock]");
    if (block) setRenameVisibility(block, c.checked);

    c.addEventListener("change", () => {
      const b = c.closest("[data-fileblock]");
      if (b) setRenameVisibility(b, c.checked);
      updateCount();
      updateRenameState();
    });
  });

  if (selectAllBtn) {
    selectAllBtn.addEventListener("click", () => {
      checks.forEach(c => {
        c.checked = true;
        const b = c.closest("[data-fileblock]");
        if (b) setRenameVisibility(b, true);
      });
      updateCount();
      updateRenameState();
    });
  }

  if (selectNoneBtn) {
    selectNoneBtn.addEventListener("click", () => {
      checks.forEach(c => {
        c.checked = false;
        const b = c.closest("[data-fileblock]");
        if (b) setRenameVisibility(b, false);
      });
      updateCount();
      updateRenameState();
    });
  }

  updateCount();
  updateRenameState();
})();
