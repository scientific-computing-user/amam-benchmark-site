(() => {
  const els = {
    reportHeadline: document.getElementById("reportHeadline"),
    reportOverview: document.getElementById("reportOverview"),
    reportMetrics: document.getElementById("reportMetrics"),
    familyChart: document.getElementById("familyChart"),
    magChart: document.getElementById("magChart"),
    subsetTableBody: document.getElementById("subsetTableBody"),
    workflowSteps: document.getElementById("workflowSteps"),
    samplePairsGrid: document.getElementById("samplePairsGrid"),
    nextStepsList: document.getElementById("nextStepsList")
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

  async function init() {
    try {
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
    } catch (error) {
      els.reportHeadline.textContent = "AMAM Benchmark Report";
      els.reportOverview.textContent = `Unable to load benchmark metadata: ${error.message}`;
      els.reportMetrics.innerHTML = "";
      els.familyChart.innerHTML = "";
      els.magChart.innerHTML = "";
      els.subsetTableBody.innerHTML = "";
      els.workflowSteps.innerHTML = "";
      els.samplePairsGrid.innerHTML = "";
    }
  }

  init();
})();
