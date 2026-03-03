(() => {
  const state = {
    dataset: null,
    filteredSubsets: [],
    compareLookup: new Map(),
    carouselTimers: []
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
    compareModal: document.getElementById("compareModal"),
    compareTitle: document.getElementById("compareTitle"),
    compareOriginalImage: document.getElementById("compareOriginalImage"),
    compareMaskImage: document.getElementById("compareMaskImage"),
    compareMaskPane: document.getElementById("compareMaskPane"),
    compareNoMask: document.getElementById("compareNoMask"),
    compareMeta: document.getElementById("compareMeta"),
    compareOpenOriginal: document.getElementById("compareOpenOriginal"),
    compareDownloadOriginal: document.getElementById("compareDownloadOriginal"),
    compareOpenMask: document.getElementById("compareOpenMask"),
    compareDownloadMask: document.getElementById("compareDownloadMask")
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

  function hiResThumbnail(url) {
    if (!url) {
      return "";
    }
    return url.replace("sz=w1000", "sz=w1800");
  }

  function initStaticContent(dataset) {
    document.title = `${dataset.shortName} Dataset Benchmark`;
    els.heroTitle.textContent = dataset.name;
    els.heroOverview.textContent = dataset.overview;

    const g = dataset.gallerySummary || {
      totalOriginals: dataset.totalImages,
      totalMasks: 0,
      totalPairs: 0
    };

    els.summaryStats.innerHTML = `
      <div class="summary-grid">
        <article class="stat-card"><span class="stat-value">${dataset.totalImages}</span><span class="stat-label">Benchmark full labels (paper)</span></article>
        <article class="stat-card"><span class="stat-value">${dataset.totalSubsets}</span><span class="stat-label">Dataset subsets</span></article>
        <article class="stat-card"><span class="stat-value">${g.totalOriginals}</span><span class="stat-label">Root/original images exposed</span></article>
        <article class="stat-card"><span class="stat-value">${g.totalPairs}</span><span class="stat-label">Detected original-mask pairs</span></article>
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

  function clearCarouselTimers() {
    state.carouselTimers.forEach(timer => clearInterval(timer));
    state.carouselTimers = [];
  }

  function moveCarousel(viewport, direction) {
    const firstSlide = viewport.querySelector(".carousel-slide");
    if (!firstSlide) {
      return;
    }

    const track = viewport.querySelector(".carousel-track");
    const gap = Number.parseFloat(window.getComputedStyle(track).columnGap || window.getComputedStyle(track).gap || "0") || 0;
    const step = firstSlide.offsetWidth + gap;

    if (direction > 0) {
      const atEnd = viewport.scrollLeft + viewport.clientWidth >= viewport.scrollWidth - step * 0.5;
      if (atEnd) {
        viewport.scrollTo({ left: 0, behavior: "smooth" });
      } else {
        viewport.scrollBy({ left: step, behavior: "smooth" });
      }
    } else {
      if (viewport.scrollLeft <= step * 0.3) {
        viewport.scrollTo({ left: Math.max(0, viewport.scrollWidth - viewport.clientWidth), behavior: "smooth" });
      } else {
        viewport.scrollBy({ left: -step, behavior: "smooth" });
      }
    }
  }

  function initCarousels() {
    clearCarouselTimers();

    els.subsetContainer.querySelectorAll(".js-carousel-shell").forEach(shell => {
      const viewport = shell.querySelector(".js-carousel");
      const nextBtn = shell.querySelector(".js-carousel-next");
      const prevBtn = shell.querySelector(".js-carousel-prev");
      if (!viewport) {
        return;
      }

      if (nextBtn) {
        nextBtn.addEventListener("click", () => moveCarousel(viewport, 1));
      }
      if (prevBtn) {
        prevBtn.addEventListener("click", () => moveCarousel(viewport, -1));
      }

      let paused = false;
      viewport.addEventListener("mouseenter", () => {
        paused = true;
      });
      viewport.addEventListener("mouseleave", () => {
        paused = false;
      });
      viewport.addEventListener("focusin", () => {
        paused = true;
      });
      viewport.addEventListener("focusout", () => {
        paused = false;
      });

      const timer = setInterval(() => {
        if (!paused) {
          moveCarousel(viewport, 1);
        }
      }, 2800);

      state.carouselTimers.push(timer);
    });
  }

  function buildGalleryFallback(subset) {
    const originals = (subset.samples || []).map(sample => ({
      id: sample.id,
      name: sample.title,
      thumbnailUrl: sample.image,
      viewUrl: sample.image,
      downloadUrl: sample.image,
      maskId: null,
      maskName: null
    }));

    return {
      originals,
      masks: [],
      pairCount: 0,
      originalCount: originals.length,
      maskCount: 0,
      hasMaskPairs: false,
      notes: "Fallback gallery from local representative samples."
    };
  }

  function renderSubsets(subsets) {
    state.compareLookup.clear();

    if (subsets.length === 0) {
      clearCarouselTimers();
      els.subsetContainer.innerHTML =
        '<article class="subset"><h3>No matching subsets</h3><p>Try broadening the filters or removing search terms.</p></article>';
      return;
    }

    const markup = subsets
      .map(subset => {
        const gallery = subset.gallery || buildGalleryFallback(subset);
        const masksById = new Map((gallery.masks || []).map(item => [item.id, item]));
        const processed = findProcessedFolder(subset.driveTree);
        const rootUrl = subset.driveTree?.url || subset.downloadUrl;

        const slides = (gallery.originals || [])
          .map(original => {
            const compareKey = `${subset.id}::${original.id}`;
            const mask = original.maskId ? masksById.get(original.maskId) || null : null;
            state.compareLookup.set(compareKey, { subset, original, mask });

            const source = original.thumbnailUrl || original.image;
            const label = original.name || original.title || original.id;
            const tag = mask
              ? '<span class="pair-tag mask">Mask Pair Available</span>'
              : '<span class="pair-tag nomask">No Paired Mask</span>';

            return `
              <article class="carousel-slide">
                <button type="button" class="carousel-card js-open-compare" data-compare-key="${escapeHtml(compareKey)}">
                  <img src="${escapeHtml(source)}" alt="${escapeHtml(label)}" loading="lazy">
                  <div class="carousel-caption">
                    <strong>${escapeHtml(label)}</strong>
                    ${tag}
                  </div>
                </button>
              </article>
            `;
          })
          .join("");

        return `
          <section id="subset-${escapeHtml(subset.id)}" class="subset reveal">
            <header class="subset-head">
              <div>
                <h3>${escapeHtml(subset.material)}</h3>
                <div class="subset-meta">
                  <span class="badge">${subset.images} images (paper)</span>
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
            <p class="category-gallery-meta">Showing ${gallery.originalCount} originals, ${gallery.maskCount} masks, ${gallery.pairCount} matched pairs. ${escapeHtml(gallery.notes || "")}</p>

            <div class="carousel-shell js-carousel-shell">
              <button type="button" class="carousel-btn js-carousel-prev" aria-label="Previous images">‹</button>
              <div class="carousel-viewport js-carousel" tabindex="0" aria-label="${escapeHtml(subset.material)} rotating image panel">
                <div class="carousel-track">
                  ${slides}
                </div>
              </div>
              <button type="button" class="carousel-btn js-carousel-next" aria-label="Next images">›</button>
            </div>
          </section>
        `;
      })
      .join("");

    els.subsetContainer.innerHTML = markup;

    els.subsetContainer.querySelectorAll(".js-open-compare").forEach(node => {
      node.addEventListener("click", event => {
        const key = event.currentTarget.getAttribute("data-compare-key");
        if (key) {
          openCompare(key);
        }
      });
    });

    initCarousels();
    observeReveals(els.subsetContainer);
  }

  function render() {
    state.filteredSubsets = getFilteredSubsets();
    renderMaterialStats(state.filteredSubsets);
    renderJump(state.filteredSubsets);
    renderSubsets(state.filteredSubsets);
  }

  function openCompare(compareKey) {
    const entry = state.compareLookup.get(compareKey);
    if (!entry) {
      return;
    }

    const { subset, original, mask } = entry;

    const originalTitle = original.name || original.title || original.id;
    const maskTitle = mask?.name || "No paired mask";

    els.compareTitle.textContent = `${subset.material} • ${subset.magnification} • ${originalTitle}`;
    els.compareOriginalImage.src = hiResThumbnail(original.thumbnailUrl || original.image || "");
    els.compareOriginalImage.alt = originalTitle;

    const originalView = original.viewUrl || original.thumbnailUrl || original.image || "#";
    const originalDownload = original.downloadUrl || original.thumbnailUrl || original.image || "#";
    els.compareOpenOriginal.href = originalView;
    els.compareDownloadOriginal.href = originalDownload;

    if (mask) {
      els.compareMaskPane.style.display = "";
      els.compareNoMask.classList.remove("show");
      els.compareMaskImage.src = hiResThumbnail(mask.thumbnailUrl || "");
      els.compareMaskImage.alt = maskTitle;
      els.compareOpenMask.hidden = false;
      els.compareDownloadMask.hidden = false;
      els.compareOpenMask.href = mask.viewUrl || mask.thumbnailUrl || "#";
      els.compareDownloadMask.href = mask.downloadUrl || mask.thumbnailUrl || "#";
    } else {
      els.compareMaskPane.style.display = "none";
      els.compareNoMask.classList.add("show");
      els.compareMaskImage.src = "";
      els.compareOpenMask.hidden = true;
      els.compareDownloadMask.hidden = true;
      els.compareOpenMask.href = "#";
      els.compareDownloadMask.href = "#";
    }

    els.compareMeta.innerHTML = `
      <div><strong>Subset:</strong> ${escapeHtml(subset.material)} (${escapeHtml(subset.condition)}, ${escapeHtml(subset.magnification)})</div>
      <div><strong>Original:</strong> ${escapeHtml(originalTitle)}</div>
      <div><strong>Mask:</strong> ${escapeHtml(maskTitle)}</div>
    `;

    if (!els.compareModal.open) {
      els.compareModal.showModal();
    }
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
      const urls = [];
      state.dataset.downloads.categories.forEach(item => {
        urls.push(item.rootUrl || item.url);
        if (item.processedUrl) {
          urls.push(item.processedUrl);
        }
      });

      urls.forEach((url, index) => {
        setTimeout(() => {
          window.open(url, "_blank", "noopener,noreferrer");
        }, index * 170);
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

    document.addEventListener("keydown", event => {
      if (!els.compareModal.open) {
        return;
      }
      if (event.key === "Escape") {
        els.compareModal.close();
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
