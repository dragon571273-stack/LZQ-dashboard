/* 配置研究辅助工具：只读行情；情景参数独立于任何原始财务模型。 */
(function (root) {
  "use strict";
  /** @param {number} rate @param {number} years @returns {number} */
  function annuity(rate, years) {
    return Math.abs(rate) < 1e-10 ? years : (1 - Math.pow(1 + rate, -years)) / rate;
  }
  /** 等额年末现金流的估值敏感性，仅用于示例，不代表任一个券。
   * @param {{kind:string,rate:number,shock:number,cash:number,years:number}} p
   * @returns {number}
   */
  function stress(p) {
    if (![p.rate, p.shock, p.cash, p.years].every(Number.isFinite) ||
      p.rate <= 0 || p.rate + p.shock <= 0 || p.cash < -1 || p.years < 1 ||
      !Number.isInteger(p.years) || !["property", "concession"].includes(p.kind)) {
      throw new RangeError("请检查贴现率、剩余年限和现金流假设。");
    }
    var ratio = p.kind === "property" ? p.rate / (p.rate + p.shock) :
      annuity(p.rate + p.shock, p.years) / annuity(p.rate, p.years);
    return (1 + p.cash) * ratio - 1;
  }
  /** @param {Array<{right?:string,ret20?:number}>} rows @param {string} right
   * @returns {{count:number,valid:number,ret20:number|null}} */
  function summarize(rows, right) {
    var group = rows.filter(function (r) { return r.right === right; });
    var values = group.map(function (r) { return r.ret20; }).filter(Number.isFinite);
    return { count: group.length, valid: values.length,
      ret20: values.length ? values.reduce(function (a, b) { return a + b; }, 0) / values.length : null };
  }
  if (typeof module !== "undefined" && module.exports) module.exports = { stress: stress, summarize: summarize };
  if (!root.document) return;
  var doc = root.document;
  // 按实际导航高度设置章节偏移，适配窄屏换行与字体缩放。
  function updateAnchorOffset() {
    var header = doc.getElementById("topbar");
    doc.documentElement.style.setProperty("--sticky-offset", (header.getBoundingClientRect().height + doc.getElementById("subbar").getBoundingClientRect().height + 20) + "px");
  }
  updateAnchorOffset();
  if (root.ResizeObserver) new ResizeObserver(updateAnchorOffset).observe(doc.getElementById("topbar"));
  /** @param {string} id @returns {HTMLInputElement} */
  function input(id) { return /** @type {HTMLInputElement} */ (doc.getElementById(id)); }
  function updateStress() {
    var output = doc.getElementById("stressResult");
    try {
      var kind = input("stressKind").value;
      input("stressYears").disabled = kind === "property";
      var value = stress({ kind: kind, rate: Number(input("stressRate").value) / 100,
        shock: Number(input("stressShock").value) / 10000,
        cash: Number(input("stressCash").value) / 100, years: Number(input("stressYears").value) });
      if (!["stressRate", "stressShock", "stressCash", "stressYears"].every(function (id) { return input(id).value !== "" && input(id).checkValidity(); })) {
        throw new RangeError("请填写允许范围内的情景参数。");
      }
      output.textContent = (value > 0 ? "+" : "") + (value * 100).toFixed(2) + "%";
      output.className = "scenario-value " + (value < 0 ? "down" : value > 0 ? "up" : "flat");
      doc.getElementById("stressMethod").textContent = kind === "property" ?
        "简化产权模型：V = C / r；永续、零增长、无杠杆。实际产权估值仍需核查土地剩余年限、资本开支与退出价值。" :
        "简化经营权模型：V = Σ C / (1+r)ᵗ；等额年末现金流、到期残值为零、无杠杆。实际项目应逐期建模。";
    } catch (error) {
      output.textContent = error instanceof Error ? error.message : "情景计算失败，请检查参数。";
      output.className = "scenario-error";
    }
  }
  var form = doc.getElementById("stressForm");
  if (form) { form.addEventListener("input", updateStress); form.addEventListener("change", updateStress); form.addEventListener("submit", function (e) { e.preventDefault(); }); updateStress(); }
  var filter = doc.getElementById("sectorResearchFilter");
  function filterSectors() {
    var value = /** @type {HTMLSelectElement} */ (filter).value;
    doc.querySelectorAll("#advicePerf tbody tr").forEach(function (row) {
      row.hidden = value !== "all" && row.getAttribute("data-role") !== value;
    });
  }
  if (filter) { filter.addEventListener("input", filterSectors); filter.addEventListener("change", filterSectors); }
  root.__DATA_READY.then(function () {
    var data = root.REITS_DATA || {};
    var rows = Array.isArray(data.reits) ? data.reits : [];
    doc.getElementById("allocationMarketDate").textContent = data.lastTradeDate || "未提供";
    doc.getElementById("allocationCoverage").textContent = rows.length + " 只";
    ["产权", "经营权"].forEach(function (right, i) {
      var s = summarize(rows, right);
      doc.getElementById("rightsSnapshot" + i).textContent = s.count + " 只 · 20日价格涨跌等权均值 " +
        (s.ret20 === null ? "暂无" : (s.ret20 > 0 ? "+" : "") + s.ret20.toFixed(2) + "%") +
        " · 有效样本 " + s.valid + "/" + s.count;
    });
    var date = data.lastTradeDate;
    var age = /^\d{4}-\d{2}-\d{2}$/.test(date || "") ? (Date.now() - Date.parse(date + "T15:00:00+08:00")) / 86400000 : Infinity;
    doc.getElementById("allocationFreshness").textContent = age > 7 ?
      "行情日期超过7个自然日或缺失，请核对更新状态；以下研究不构成实时评级。" :
      "行情按交易日更新；研究结论需结合最新公告复核。价格表现不等同于估值或含分红回报。";
  }).catch(function () {
    doc.getElementById("allocationFreshness").textContent = "行情暂不可用，研究正文仍可阅读；当前市场判断待数据恢复后复核。";
    // 核心行情加载失败时，独立开放静态研究，避免正文被默认页面隐藏。
    doc.querySelectorAll(".page").forEach(function (page) { page.hidden = page.id !== "pg-advice"; });
    doc.getElementById("topbar").dataset.cur = "advice";
    doc.getElementById("subbar").dataset.cur = "advice";
    doc.querySelectorAll("#tbNav button").forEach(function (button) {
      var active = button.getAttribute("data-pg") === "advice";
      button.classList.toggle("on", active);
      if (active) button.setAttribute("aria-current", "page"); else button.removeAttribute("aria-current");
      button.disabled = !active;
    });
    doc.querySelectorAll("#adviceSub button").forEach(function (button) {
      button.addEventListener("click", function () {
        var section = doc.getElementById(button.getAttribute("data-scroll"));
        if (section && root.ReitsWorkspace) root.ReitsWorkspace.selectAdviceForTarget(section);
        if (section) section.scrollIntoView();
        doc.querySelectorAll("#adviceSub button").forEach(function (other) {
          other.classList.toggle("on", other === button);
          if (other === button) other.setAttribute("aria-current", "page"); else other.removeAttribute("aria-current");
        });
      });
    });
  });
})(typeof window === "undefined" ? globalThis : window);
