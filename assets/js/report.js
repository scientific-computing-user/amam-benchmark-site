(() => {
  const state = {
    modelRows: []
  };

  const GROUP_LABELS = {
    classical: "Classical baselines",
    deep_general: "Deep supervised (general)",
    deep_metallography: "Deep supervised (metallography)",
    foundation_edge: "Foundation/edge add-ons"
  };

  const CLASSICAL_METHOD_NAMES = {
    svm_pixel: "Linear SVM (pixel features)",
    rf_pixel: "RF (pixel features)",
    gmm_rgb: "GMM-RGB",
    gabor_kmeans: "Gabor+KMeans",
    slic_cluster: "SLIC+KMeans",
    kmeans_rgb: "KMeans-RGB",
    felzenszwalb_cluster: "Felzenszwalb+GMM",
    lbp_kmeans: "LBP+KMeans",
    canny_watershed: "Canny+Watershed",
    sobel_watershed: "Sobel+Watershed"
  };

  const CLASSICAL_CATEGORY_NAMES = {
    metallography_learned: "Metallography-learned",
    contour_region: "Contour/region",
    baseline: "Baseline",
    texture: "Texture",
    edge: "Edge"
  };

  const FOUNDATION_MODEL_NAMES = {
    sam_vit_base: "SAM ViT-Base (auto-mask)",
    slimsam_50: "SlimSAM-50 (auto-mask)",
    slimsam_77: "SlimSAM-77 (auto-mask)",
    texturesam_03: "TextureSAM-0.3 (auto-mask)",
    hed_watershed: "HED + Watershed",
    pidi_watershed: "PidiNet + Watershed"
  };

  const FOUNDATION_CATEGORY_NAMES = {
    foundation_sam: "Foundation SAM",
    deep_edge: "Deep Edge"
  };

  const els = {
    reportHeadline: document.getElementById("reportHeadline"),
    reportOverview: document.getElementById("reportOverview"),
    reportMetrics: document.getElementById("reportMetrics"),
    familyChart: document.getElementById("familyChart"),
    magChart: document.getElementById("magChart"),
    subsetTableBody: document.getElementById("subsetTableBody"),
    workflowSteps: document.getElementById("workflowSteps"),
    samplePairsGrid: document.getElementById("samplePairsGrid"),
    nextStepsList: document.getElementById("nextStepsList"),
    resultsSummary: document.getElementById("resultsSummary"),
    resultsGroupFilter: document.getElementById("resultsGroupFilter"),
    resultsSortBy: document.getElementById("resultsSortBy"),
    resultsSearch: document.getElementById("resultsSearch"),
    resultsStatus: document.getElementById("resultsStatus"),
    resultsTableBody: document.getElementById("resultsTableBody")
  };

  function escapeHtml(value) {
    return String(value)
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#39;");
  }

  function toAssetUrl(path) {
    return encodeURI(path);
  }

  function humanizeToken(value) {
    return String(value || "")
      .replaceAll("_", " ")
      .replaceAll("-", " ")
      .replace(/\b\w/g, char => char.toUpperCase());
  }

  function parseCsv(text) {
    const lines = String(text || "")
      .trim()
      .split(/\r?\n/)
      .filter(Boolean);
    if (lines.length < 2) {
      return [];
    }

    const headers = lines[0].split(",").map(header => header.trim());
    return lines.slice(1).map(line => {
      const cells = line.split(",");
      return headers.reduce((acc, header, idx) => {
        acc[header] = (cells[idx] || "").trim();
        return acc;
      }, {});
    });
  }

  function toNumber(value) {
    const n = Number.parseFloat(value);
    return Number.isFinite(n) ? n : NaN;
  }

  function formatMetric(value) {
    return Number.isFinite(value) ? value.toFixed(4) : "—";
  }

  function formatGroupLabel(groupKey) {
    return GROUP_LABELS[groupKey] || humanizeToken(groupKey);
  }

  function getFilteredAndSortedResults() {
    const groupFilter = els.resultsGroupFilter.value;
    const search = els.resultsSearch.value.trim().toLowerCase();
    const sortBy = els.resultsSortBy.value;

    const filtered = state.modelRows.filter(row => {
      const groupMatch = groupFilter === "all" || row.groupKey === groupFilter;
      const haystack = [row.model, row.groupLabel, row.category].join(" ").toLowerCase();
      const searchMatch = search.length === 0 || haystack.includes(search);
      return groupMatch && searchMatch;
    });

    filtered.sort((a, b) => {
      const delta = (b[sortBy] || 0) - (a[sortBy] || 0);
      if (delta !== 0) {
        return delta;
      }
      return (b.miou || 0) - (a.miou || 0);
    });

    return filtered;
  }

  function getSubsetPairs(subset) {
    const gallery = subset.gallery || { originals: [], masks: [] };
    const masksById = new Map(
      (gallery.masks || [])
        .filter(item => item && item.id && (item.path || item.thumbnailUrl || item.downloadUrl))
        .map(item => [item.id, item])
    );

    return (gallery.originals || []).reduce((acc, original) => {
      const originalPath = original?.path || original?.thumbnailUrl || original?.downloadUrl;
      if (!originalPath || !original?.maskId) {
        return acc;
      }
      const mask = masksById.get(original.maskId);
      if (!mask) {
        return acc;
      }
      acc.push({ original, mask });
      return acc;
    }, []);
  }

  function groupByPairs(items, key) {
    const grouped = items.reduce((acc, subset) => {
      const groupKey = subset[key];
      const count = getSubsetPairs(subset).length;
      acc[groupKey] = (acc[groupKey] || 0) + count;
      return acc;
    }, {});

    return Object.entries(grouped).sort((a, b) => b[1] - a[1]);
  }

  function renderBars(container, rows) {
    const max = Math.max(...rows.map(([, value]) => value), 1);
    const total = rows.reduce((sum, [, value]) => sum + value, 0) || 1;

    container.innerHTML = rows
      .map(([label, value]) => {
        const pct = Math.round((value / total) * 100);
        const width = (value / max) * 100;
        return `
          <div class="bar-row">
            <span class="bar-label">${escapeHtml(label)}</span>
            <span class="bar-track"><span class="bar-fill" style="width:${width}%"></span></span>
            <span class="bar-value">${value} (${pct}%)</span>
          </div>
        `;
      })
      .join("");
  }

  function renderMetrics(dataset, subsets) {
    const pairedSubsets = subsets.filter(subset => getSubsetPairs(subset).length > 0);
    const totalPairs = pairedSubsets.reduce((sum, subset) => sum + getSubsetPairs(subset).length, 0);
    const totalOriginals = pairedSubsets.reduce((sum, subset) => sum + (subset.gallery?.originalCount || 0), 0);
    const pairCoverage = totalOriginals > 0 ? (totalPairs / totalOriginals) * 100 : 0;
    const uniqueMaterials = new Set(pairedSubsets.map(subset => subset.material)).size;
    const uniqueFamilies = new Set(pairedSubsets.map(subset => subset.family)).size;
    const uniqueConditions = new Set(pairedSubsets.map(subset => subset.condition)).size;
    const uniqueMagnifications = new Set(pairedSubsets.map(subset => subset.magnification)).size;
    const uniquePhases = new Set(pairedSubsets.flatMap(subset => subset.phases || [])).size;
    const multiMagMaterials = Object.values(
      pairedSubsets.reduce((acc, subset) => {
        if (!acc[subset.material]) {
          acc[subset.material] = new Set();
        }
        acc[subset.material].add(subset.magnification);
        return acc;
      }, {})
    ).filter(set => set.size > 1).length;

    els.reportHeadline.textContent = `${dataset.name} Benchmark Report (${totalPairs} labeled pairs)`;
    els.reportOverview.textContent =
      `${dataset.overview || ""} This page verifies benchmark claims against the local AMAM release metadata and shows where AMAM is strong and where protocol governance is still needed.`;

    const metrics = [
      { value: totalPairs, label: "Matched original-mask tuples" },
      { value: `${pairCoverage.toFixed(1)}%`, label: "Pair coverage over local originals" },
      { value: pairedSubsets.length, label: "Included subsets with valid pairs" },
      { value: uniqueMaterials, label: "Distinct material datasets" },
      { value: uniquePhases, label: "Distinct phase labels across subsets" },
      { value: uniqueMagnifications, label: "Magnification regimes represented" },
      { value: uniqueFamilies, label: "Material families represented" },
      { value: uniqueConditions, label: "Processing conditions represented" },
      { value: multiMagMaterials, label: "Materials with multi-magnification coverage" }
    ];

    els.reportMetrics.innerHTML = metrics
      .map(
        metric => `
          <article class="metric-tile">
            <span class="metric-value">${escapeHtml(metric.value)}</span>
            <span class="metric-label">${escapeHtml(metric.label)}</span>
          </article>
        `
      )
      .join("");

    renderBars(els.familyChart, groupByPairs(pairedSubsets, "family"));
    renderBars(els.magChart, groupByPairs(pairedSubsets, "magnification"));
  }

  function renderSubsetTable(subsets) {
    const rows = subsets
      .map(subset => {
        const pairs = getSubsetPairs(subset).length;
        if (pairs === 0) {
          return null;
        }
        const originals = subset.gallery?.originalCount || 0;
        const coverage = originals > 0 ? Math.round((pairs / originals) * 100) : 0;
        return { subset, pairs, coverage };
      })
      .filter(Boolean)
      .sort((a, b) => b.pairs - a.pairs);

    els.subsetTableBody.innerHTML = rows
      .map(
        ({ subset, pairs, coverage }) => `
          <tr>
            <td>${escapeHtml(subset.material)}</td>
            <td>${escapeHtml(subset.family)}</td>
            <td>${escapeHtml(subset.condition)}</td>
            <td>${escapeHtml(subset.magnification)}</td>
            <td>${pairs}</td>
            <td>${coverage}%</td>
          </tr>
        `
      )
      .join("");
  }

  function renderWorkflow(method) {
    const steps = method?.steps || [];
    els.workflowSteps.innerHTML = steps
      .map(step => `<li>${escapeHtml(step)}</li>`)
      .join("");
  }

  function renderSamples(subsets) {
    const sampleCards = subsets
      .map(subset => {
        const pairs = getSubsetPairs(subset);
        if (pairs.length === 0) {
          return null;
        }

        const pair = pairs[0];
        const originalPath = toAssetUrl(pair.original.path || pair.original.thumbnailUrl || pair.original.downloadUrl || "");
        const maskPath = toAssetUrl(pair.mask.path || pair.mask.thumbnailUrl || pair.mask.downloadUrl || "");
        const originals = subset.gallery?.originalCount || 0;
        const coverage = originals > 0 ? Math.round((pairs.length / originals) * 100) : 0;

        return `
          <article class="pair-card">
            <div class="pair-head">
              <h3>${escapeHtml(subset.material)} · ${escapeHtml(subset.magnification)}</h3>
              <span class="pair-meta">${pairs.length} pairs · ${coverage}% coverage</span>
            </div>
            <div class="pair-preview">
              <figure>
                <img src="${escapeHtml(originalPath)}" alt="${escapeHtml(subset.material)} original micrograph" loading="lazy">
                <figcaption>Original</figcaption>
              </figure>
              <figure>
                <img src="${escapeHtml(maskPath)}" alt="${escapeHtml(subset.material)} label mask" loading="lazy">
                <figcaption>Mask</figcaption>
              </figure>
            </div>
            <div class="pair-actions">
              <a class="btn btn-secondary" href="index.html#subset-${escapeHtml(subset.id)}">Open Subset in Explorer</a>
            </div>
          </article>
        `;
      })
      .filter(Boolean);

    els.samplePairsGrid.innerHTML = sampleCards.join("");
  }

  function renderDynamicNotes(dataset) {
    if (!dataset.excludedSubsets || dataset.excludedSubsets.length === 0) {
      return;
    }

    const li = document.createElement("li");
    li.textContent = `Local strict rule excluded subsets without a detectable label subfolder: ${dataset.excludedSubsets.join(", ")}.`;
    els.nextStepsList.append(li);
  }

  function renderResultsSummary() {
    if (!els.resultsSummary) {
      return;
    }

    const rows = state.modelRows;
    const counts = rows.reduce((acc, row) => {
      acc[row.groupKey] = (acc[row.groupKey] || 0) + 1;
      return acc;
    }, {});

    const topOverall = [...rows].sort((a, b) => (b.miou || 0) - (a.miou || 0))[0];

    els.resultsSummary.innerHTML = `
      <article class="metric-tile result-metric">
        <span class="metric-value">${rows.length}</span>
        <span class="metric-label">Total benchmarked models</span>
      </article>
      <article class="metric-tile result-metric">
        <span class="metric-value">${counts.classical || 0}</span>
        <span class="metric-label">Classical baselines</span>
      </article>
      <article class="metric-tile result-metric">
        <span class="metric-value">${(counts.deep_general || 0) + (counts.deep_metallography || 0)}</span>
        <span class="metric-label">Supervised deep models</span>
      </article>
      <article class="metric-tile result-metric">
        <span class="metric-value">${counts.foundation_edge || 0}</span>
        <span class="metric-label">Foundation/edge add-ons</span>
      </article>
      <article class="metric-tile result-metric result-metric-wide">
        <span class="metric-value">${topOverall ? topOverall.miou.toFixed(4) : "—"}</span>
        <span class="metric-label">Best mIoU overall: ${topOverall ? escapeHtml(topOverall.model) : "N/A"}</span>
      </article>
    `;
  }

  function renderResultsTable() {
    if (!els.resultsTableBody) {
      return;
    }

    const rows = getFilteredAndSortedResults();
    const sortByLabel = els.resultsSortBy.value === "pixelAcc" ? "Pixel Accuracy" : els.resultsSortBy.value.toUpperCase();

    if (rows.length === 0) {
      els.resultsTableBody.innerHTML = `
        <tr>
          <td colspan="7">No models match the current filters.</td>
        </tr>
      `;
      if (els.resultsStatus) {
        els.resultsStatus.textContent = "No models match the current filter/search.";
      }
      return;
    }

    els.resultsTableBody.innerHTML = rows
      .map(
        (row, idx) => `
          <tr class="${idx < 3 ? "top-row" : ""}">
            <td>${idx + 1}</td>
            <td>${escapeHtml(row.model)}</td>
            <td>${escapeHtml(row.groupLabel)}</td>
            <td>${escapeHtml(row.category)}</td>
            <td>${formatMetric(row.miou)}</td>
            <td>${formatMetric(row.dice)}</td>
            <td>${formatMetric(row.pixelAcc)}</td>
          </tr>
        `
      )
      .join("");

    if (els.resultsStatus) {
      els.resultsStatus.textContent = `Showing ${rows.length} of ${state.modelRows.length} models. Sorted by ${sortByLabel}.`;
    }
  }

  function bindResultsControls() {
    if (!els.resultsGroupFilter || !els.resultsSortBy || !els.resultsSearch) {
      return;
    }

    els.resultsGroupFilter.addEventListener("change", renderResultsTable);
    els.resultsSortBy.addEventListener("change", renderResultsTable);
    els.resultsSearch.addEventListener("input", renderResultsTable);
  }

  async function loadModelResults() {
    const [classicalCsv, deepCsv, foundationCsv] = await Promise.all([
      fetch("assets/data/results/benchmark_summary.csv").then(response => {
        if (!response.ok) {
          throw new Error(`Failed loading classical results (${response.status})`);
        }
        return response.text();
      }),
      fetch("assets/data/results/deep_macro_over_subsets.csv").then(response => {
        if (!response.ok) {
          throw new Error(`Failed loading deep results (${response.status})`);
        }
        return response.text();
      }),
      fetch("assets/data/results/foundation_edge_summary.csv").then(response => {
        if (!response.ok) {
          throw new Error(`Failed loading foundation/edge results (${response.status})`);
        }
        return response.text();
      })
    ]);

    const classicalRows = parseCsv(classicalCsv).map(row => ({
      model: CLASSICAL_METHOD_NAMES[row.method] || humanizeToken(row.method),
      groupKey: "classical",
      groupLabel: formatGroupLabel("classical"),
      category: CLASSICAL_CATEGORY_NAMES[row.category] || humanizeToken(row.category),
      miou: toNumber(row.miou),
      dice: toNumber(row.dice),
      pixelAcc: toNumber(row.pixel_acc)
    }));

    const deepRows = parseCsv(deepCsv).map(row => {
      const groupKey = row.group === "metallography" ? "deep_metallography" : "deep_general";
      return {
        model: row.display_name || humanizeToken(row.model_id),
        groupKey,
        groupLabel: formatGroupLabel(groupKey),
        category: humanizeToken(row.category),
        miou: toNumber(row.miou),
        dice: toNumber(row.dice),
        pixelAcc: toNumber(row.pixel_acc)
      };
    });

    const foundationRows = parseCsv(foundationCsv).map(row => ({
      model: FOUNDATION_MODEL_NAMES[row.model_id] || humanizeToken(row.model_id),
      groupKey: "foundation_edge",
      groupLabel: formatGroupLabel("foundation_edge"),
      category: FOUNDATION_CATEGORY_NAMES[row.category] || humanizeToken(row.category),
      miou: toNumber(row.miou),
      dice: toNumber(row.dice),
      pixelAcc: toNumber(row.pixel_acc)
    }));

    const merged = [...classicalRows, ...deepRows, ...foundationRows].filter(
      row => Number.isFinite(row.miou) && Number.isFinite(row.dice) && Number.isFinite(row.pixelAcc)
    );

    merged.sort((a, b) => b.miou - a.miou);
    return merged;
  }

  async function init() {
    try {
      bindResultsControls();

      const response = await fetch("assets/data/amam-dataset.json");
      if (!response.ok) {
        throw new Error(`Failed loading dataset metadata (${response.status})`);
      }

      const dataset = await response.json();
      const subsets = dataset.subsets || [];

      renderMetrics(dataset, subsets);
      renderSubsetTable(subsets);
      renderWorkflow(dataset.method || {});
      renderSamples(subsets);
      renderDynamicNotes(dataset);

      state.modelRows = await loadModelResults();
      renderResultsSummary();
      renderResultsTable();
    } catch (error) {
      els.reportHeadline.textContent = "AMAM Benchmark Report";
      els.reportOverview.textContent = `Unable to load benchmark metadata: ${error.message}`;
      els.reportMetrics.innerHTML = "";
      els.familyChart.innerHTML = "";
      els.magChart.innerHTML = "";
      els.subsetTableBody.innerHTML = "";
      els.workflowSteps.innerHTML = "";
      els.samplePairsGrid.innerHTML = "";
      if (els.resultsSummary) {
        els.resultsSummary.innerHTML = "";
      }
      if (els.resultsStatus) {
        els.resultsStatus.textContent = `Unable to load model results: ${error.message}`;
      }
      if (els.resultsTableBody) {
        els.resultsTableBody.innerHTML = "";
      }
    }
  }

  init();
})();
