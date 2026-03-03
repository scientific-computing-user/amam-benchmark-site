(() => {
  const state = {
    dataset: null,
    filteredSubsets: [],
    visibleSamples: [],
    lightboxIndex: 0
  };

  const els = {
    heroTitle: document.getElementById("heroTitle"),
    heroOverview: document.getElementById("heroOverview"),
    summaryStats: document.getElementById("summaryStats"),
    methodSteps: document.getElementById("methodSteps"),
    materialBars: document.getElementById("materialBars"),
    driveMatrix: document.getElementById("driveMatrix"),
    subsetJump: document.getElementById("subsetJump"),
    subsetContainer: document.getElementById("subsetContainer"),
    familyFilter: document.getElementById("familyFilter"),
    magFilter: document.getElementById("magFilter"),
    searchInput: document.getElementById("searchInput"),
    categoryDownloadSelect: document.getElementById("categoryDownloadSelect"),
    downloadCategoryBtn: document.getElementById("downloadCategoryBtn"),
    downloadAllBtn: document.getElementById("downloadAllBtn"),
    downloadManifestBtn: document.getElementById("downloadManifestBtn"),
    lightbox: document.getElementById("lightbox"),
    lightboxImage: document.getElementById("lightboxImage"),
    lightboxCaption: document.getElementById("lightboxCaption"),
    lightboxProps: document.getElementById("lightboxProps"),
    lightboxPrev: document.getElementById("lightboxPrev"),
    lightboxNext: document.getElementById("lightboxNext")
  };

  const observer = new IntersectionObserver(
    entries => {
      entries.forEach(entry => {
        if (entry.isIntersecting) {
          entry.target.classList.add("show");
        }
      });
    },
    { threshold: 0.15 }
  );

  function escapeHtml(value) {
    return String(value)
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#39;");
  }

  function observeReveals(scope = document) {
    scope.querySelectorAll(".reveal").forEach(node => observer.observe(node));
  }

  function initStaticContent(dataset) {
    document.title = `${dataset.shortName} Dataset Benchmark`;
    els.heroTitle.textContent = dataset.name;
    els.heroOverview.textContent = dataset.overview;

    els.summaryStats.innerHTML = `
      <div class="summary-grid">
        <article class="stat-card"><span class="stat-value">${dataset.totalImages}</span><span class="stat-label">Fully labeled images</span></article>
        <article class="stat-card"><span class="stat-value">${dataset.totalSubsets}</span><span class="stat-label">Dataset subsets</span></article>
        <article class="stat-card"><span class="stat-value">${dataset.materialFamilies.length}</span><span class="stat-label">Material families</span></article>
        <article class="stat-card"><span class="stat-value">${dataset.method.tool}</span><span class="stat-label">Annotation platform</span></article>
      </div>
    `;

    els.methodSteps.innerHTML = dataset.method.steps
      .map(
        (step, idx) => `
          <article class="method-step">
            <span class="step-index">${idx + 1}</span>
            <p>${escapeHtml(step)}</p>
          </article>
        `
      )
      .join("");
  }

  function initDownloadSelect(dataset) {
    els.categoryDownloadSelect.innerHTML = dataset.downloads.categories
      .map(
        category =>
          `<option value="${escapeHtml(category.rootUrl || category.url)}">${escapeHtml(category.name)}</option>`
      )
      .join("");
  }

  function flattenDriveFolders(node) {
    if (!node) {
      return [];
    }
    const children = Array.isArray(node.children) ? node.children : [];
    return children.reduce((acc, child) => {
      acc.push(child);
      return acc.concat(flattenDriveFolders(child));
    }, []);
  }

  function findProcessedFolder(node) {
    const folders = flattenDriveFolders(node);
    return folders.find(folder => folder.name.toLowerCase().includes("processed"));
  }

  function renderDriveTree(node) {
    if (!node) {
      return "";
    }
    const children = Array.isArray(node.children) ? node.children : [];
    if (children.length === 0) {
      return "";
    }
    return `
      <ul class="drive-tree">
        ${children
          .map(
            child => `
              <li>
                <div class="drive-tree-item">
                  <a target="_blank" rel="noopener noreferrer" href="${escapeHtml(child.url)}">${escapeHtml(child.name)}</a>
                  <span>${Number(child.imageCount || 0)} images</span>
                </div>
                ${renderDriveTree(child)}
              </li>
            `
          )
          .join("")}
      </ul>
    `;
  }

  function renderDriveMatrix(dataset) {
    if (!els.driveMatrix) {
      return;
    }

    const rows = dataset.subsets
      .map(subset => {
        const root = subset.driveTree;
        const processed = findProcessedFolder(root);
        const rootUrl = root?.url || subset.downloadUrl;
        const driveNote = dataset.driveStructureNote
          ? `<p class="drive-note">${escapeHtml(dataset.driveStructureNote)}</p>`
          : "";

        return `
          <article class="drive-row reveal">
            <div class="drive-row-head">
              <h3>${escapeHtml(subset.material)} · ${escapeHtml(subset.magnification)}</h3>
              <div class="drive-row-links">
                <a class="btn btn-ghost" target="_blank" rel="noopener noreferrer" href="${escapeHtml(rootUrl)}">Open Root</a>
                ${
                  processed
                    ? `<a class="btn btn-secondary" target="_blank" rel="noopener noreferrer" href="${escapeHtml(processed.url)}">Open Processed/Masks</a>`
                    : ""
                }
              </div>
            </div>
            ${driveNote}
            <p class="drive-note">Expected benchmark images: ${subset.images}. Root currently exposes ${Number(root?.imageCount || 0)} images.</p>
            ${renderDriveTree(root)}
          </article>
        `;
      })
      .join("");

    els.driveMatrix.innerHTML = rows;
    observeReveals(els.driveMatrix);
  }

  function initFilters(dataset) {
    const families = [...new Set(dataset.subsets.map(item => item.family))].sort();
    const magnifications = [...new Set(dataset.subsets.map(item => item.magnification))].sort();

    families.forEach(family => {
      els.familyFilter.insertAdjacentHTML(
        "beforeend",
        `<option value="${escapeHtml(family)}">${escapeHtml(family)}</option>`
      );
    });

    magnifications.forEach(mag => {
      els.magFilter.insertAdjacentHTML(
        "beforeend",
        `<option value="${escapeHtml(mag)}">${escapeHtml(mag)}</option>`
      );
    });
  }

  function getFilteredSubsets() {
    const family = els.familyFilter.value;
    const mag = els.magFilter.value;
    const query = els.searchInput.value.trim().toLowerCase();

    return state.dataset.subsets.filter(subset => {
      const familyMatch = family === "all" || subset.family === family;
      const magMatch = mag === "all" || subset.magnification === mag;
      const queryHaystack = [
        subset.material,
        subset.family,
        subset.condition,
        subset.description,
        subset.annotationNotes,
        ...subset.phases
      ]
        .join(" ")
        .toLowerCase();

      const queryMatch = query.length === 0 || queryHaystack.includes(query);
      return familyMatch && magMatch && queryMatch;
    });
  }

  function renderMaterialStats(subsets) {
    const grouped = subsets.reduce((acc, subset) => {
      acc[subset.family] = (acc[subset.family] || 0) + subset.images;
      return acc;
    }, {});

    const total = Object.values(grouped).reduce((sum, count) => sum + count, 0) || 1;
    const cards = Object.entries(grouped)
      .sort(([a], [b]) => a.localeCompare(b))
      .map(([family, count]) => {
        const pct = Math.round((count / total) * 100);
        return `
          <article class="material-card">
            <div class="material-meta">
              <strong>${escapeHtml(family)}</strong>
              <span>${count} images (${pct}%)</span>
            </div>
            <div class="progress"><span style="width:${pct}%"></span></div>
          </article>
        `;
      });

    els.materialBars.innerHTML = cards.join("");
  }

  function renderJump(subsets) {
    els.subsetJump.innerHTML = subsets
      .map(
        subset =>
          `<a class="chip" href="#subset-${escapeHtml(subset.id)}">${escapeHtml(subset.material)} · ${escapeHtml(subset.magnification)}</a>`
      )
      .join("");
  }

  function renderSubsets(subsets) {
    if (subsets.length === 0) {
      state.visibleSamples = [];
      els.subsetContainer.innerHTML =
        '<article class="subset"><h3>No matching subsets</h3><p>Try broadening the filters or removing search terms.</p></article>';
      return;
    }

    const sampleRefs = [];
    const markup = subsets
      .map(subset => {
        const processed = findProcessedFolder(subset.driveTree);
        const rootUrl = subset.driveTree?.url || subset.downloadUrl;
        const subsetHeader = `
          <header class="subset-head">
            <div>
              <h3>${escapeHtml(subset.material)}</h3>
              <div class="subset-meta">
                <span class="badge">${subset.images} images</span>
                <span class="badge">${escapeHtml(subset.family)}</span>
                <span class="badge">${escapeHtml(subset.condition)}</span>
                <span class="badge">${escapeHtml(subset.magnification)}</span>
              </div>
            </div>
            <div class="subset-actions">
              <a class="btn btn-ghost" target="_blank" rel="noopener noreferrer" href="${escapeHtml(rootUrl)}">Open Root</a>
              ${
                processed
                  ? `<a class="btn btn-secondary" target="_blank" rel="noopener noreferrer" href="${escapeHtml(processed.url)}">Open Processed/Masks</a>`
                  : `<a class="btn btn-secondary" target="_blank" rel="noopener noreferrer" href="${escapeHtml(subset.downloadUrl)}">Open Category</a>`
              }
            </div>
          </header>
          <p>${escapeHtml(subset.description)}</p>
          <p><strong>Annotation notes:</strong> ${escapeHtml(subset.annotationNotes)}</p>
          <p><strong>Phase classes:</strong> ${subset.phases.map(phase => escapeHtml(phase)).join(", ")}</p>
        `;

        const sampleCards = subset.samples
          .map(sample => {
            const index = sampleRefs.push({ subset, sample }) - 1;
            const propMarkup = Object.entries(sample.properties)
              .slice(0, 5)
              .map(
                ([key, value]) =>
                  `<div><dt>${escapeHtml(key)}</dt><dd>${escapeHtml(value)}</dd></div>`
              )
              .join("");

            return `
              <article class="sample-card">
                <img src="${escapeHtml(sample.image)}" alt="${escapeHtml(sample.title)}" data-sample-index="${index}" class="js-open-lightbox">
                <div class="sample-body">
                  <h4>${escapeHtml(sample.title)}</h4>
                  <span class="sample-kind">${escapeHtml(sample.kind)}</span>
                  <dl class="props">${propMarkup}</dl>
                  <div class="sample-actions">
                    <button type="button" class="btn btn-ghost js-open-lightbox" data-sample-index="${index}">Enlarge</button>
                    <a class="btn btn-ghost" href="${escapeHtml(sample.image)}" download>Download Sample</a>
                  </div>
                </div>
              </article>
            `;
          })
          .join("");

        return `
          <section id="subset-${escapeHtml(subset.id)}" class="subset reveal">
            ${subsetHeader}
            <div class="sample-grid">${sampleCards}</div>
          </section>
        `;
      })
      .join("");

    state.visibleSamples = sampleRefs;
    els.subsetContainer.innerHTML = markup;

    els.subsetContainer.querySelectorAll(".js-open-lightbox").forEach(node => {
      node.addEventListener("click", event => {
        const target = event.currentTarget;
        const index = Number(target.getAttribute("data-sample-index"));
        if (!Number.isNaN(index)) {
          openLightbox(index);
        }
      });
    });

    observeReveals(els.subsetContainer);
  }

  function render() {
    state.filteredSubsets = getFilteredSubsets();
    renderMaterialStats(state.filteredSubsets);
    renderJump(state.filteredSubsets);
    renderSubsets(state.filteredSubsets);
  }

  function fillLightbox(index) {
    const entry = state.visibleSamples[index];
    if (!entry) {
      return;
    }

    const { subset, sample } = entry;
    const caption = `${sample.title} • ${subset.material} • ${sample.kind}`;

    els.lightboxImage.src = sample.image;
    els.lightboxImage.alt = sample.title;
    els.lightboxCaption.textContent = caption;

    els.lightboxProps.innerHTML = Object.entries(sample.properties)
      .map(
        ([key, value]) =>
          `<div><strong>${escapeHtml(key)}:</strong> ${escapeHtml(value)}</div>`
      )
      .join("");

    state.lightboxIndex = index;
  }

  function openLightbox(index) {
    fillLightbox(index);
    if (!els.lightbox.open) {
      els.lightbox.showModal();
    }
  }

  function navLightbox(step) {
    if (state.visibleSamples.length === 0) {
      return;
    }
    const total = state.visibleSamples.length;
    const next = (state.lightboxIndex + step + total) % total;
    fillLightbox(next);
  }

  function bindEvents() {
    [els.familyFilter, els.magFilter].forEach(select => {
      select.addEventListener("change", render);
    });
    els.searchInput.addEventListener("input", render);

    els.downloadCategoryBtn.addEventListener("click", () => {
      const url = els.categoryDownloadSelect.value;
      if (url) {
        window.open(url, "_blank", "noopener,noreferrer");
      }
    });

    els.downloadAllBtn.addEventListener("click", () => {
      const urls = state.dataset.downloads.categories.map(item => item.url);
      urls.forEach((url, index) => {
        setTimeout(() => {
          window.open(url, "_blank", "noopener,noreferrer");
        }, index * 180);
      });
    });

    els.downloadManifestBtn.addEventListener("click", () => {
      const blob = new Blob([JSON.stringify(state.dataset, null, 2)], {
        type: "application/json"
      });
      const blobUrl = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = blobUrl;
      anchor.download = "amam-dataset-manifest.json";
      document.body.append(anchor);
      anchor.click();
      anchor.remove();
      setTimeout(() => URL.revokeObjectURL(blobUrl), 800);
    });

    els.lightboxPrev.addEventListener("click", () => navLightbox(-1));
    els.lightboxNext.addEventListener("click", () => navLightbox(1));

    document.addEventListener("keydown", event => {
      if (!els.lightbox.open) {
        return;
      }
      if (event.key === "ArrowRight") {
        navLightbox(1);
      }
      if (event.key === "ArrowLeft") {
        navLightbox(-1);
      }
      if (event.key === "Escape") {
        els.lightbox.close();
      }
    });
  }

  async function init() {
    try {
      const response = await fetch("assets/data/amam-dataset.json");
      if (!response.ok) {
        throw new Error(`Failed loading dataset (${response.status})`);
      }
      state.dataset = await response.json();

      initStaticContent(state.dataset);
      initDownloadSelect(state.dataset);
      initFilters(state.dataset);
      renderDriveMatrix(state.dataset);
      bindEvents();
      render();
      observeReveals(document);
    } catch (error) {
      els.subsetContainer.innerHTML = `<article class="subset"><h3>Failed to load dataset</h3><p>${escapeHtml(error.message)}</p></article>`;
    }
  }

  init();
})();
