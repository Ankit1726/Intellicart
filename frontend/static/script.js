const form = document.getElementById("customerForm");
const resultEmpty = document.getElementById("resultEmpty");
const resultContent = document.getElementById("resultContent");
const submitBtn = form.querySelector(".submit-btn");

const RING_RADIUS = { 3: 60, 2: 100, 1: 100, 0: 140 };

function buildPayload(formData) {
  const get = (name) => formData.get(name);
  const education = get("Education");
  const living = get("Living_Partner");

  return {
    Income: Number(get("Income")),
    Recency: Number(get("Recency")),
    NumDealsPurchases: Number(get("NumDealsPurchases")),
    NumWebPurchases: Number(get("NumWebPurchases")),
    NumCatalogPurchases: Number(get("NumCatalogPurchases")),
    NumStorePurchases: Number(get("NumStorePurchases")),
    NumWebVisitsMonth: Number(get("NumWebVisitsMonth")),
    Complain: formData.has("Complain") ? 1 : 0,
    Response: formData.has("Response") ? 1 : 0,
    Age: Number(get("Age")),
    Customer_TenureDay: Number(get("Customer_TenureDay")),
    Total_Spent: Number(get("Total_Spent")),
    Total_Children: Number(get("Total_Children")),
    Education_Graduate: education === "Graduate" ? 1 : 0,
    Education_Postgraduate: education === "Postgraduate" ? 1 : 0,
    Education_Undergraduate: education === "Undergraduate" ? 1 : 0,
    Living_Partner_Alone: living === "Alone" ? 1 : 0,
    Living_Partner_Partner: living === "Partner" ? 1 : 0,
  };
}

function animateNumber(el, target, duration = 900) {
  const start = performance.now();
  const from = 0;
  function tick(now) {
    const t = Math.min(1, (now - start) / duration);
    const eased = 1 - Math.pow(1 - t, 3);
    el.textContent = Math.round((from + (target - from) * eased) * 100);
    if (t < 1) requestAnimationFrame(tick);
    else el.textContent = Math.round(target * 100);
  }
  requestAnimationFrame(tick);
}

function placeDot(cluster, score) {
  const dot = document.getElementById("customerDot");
  const radius = RING_RADIUS[cluster];
  // angle nudged by score for a touch of organic placement
  const angle = (-90 + score * 300 - 150) * (Math.PI / 180);
  const cx = 160 + radius * Math.cos(angle);
  const cy = 160 + radius * Math.sin(angle);
  dot.setAttribute("cx", cx.toFixed(1));
  dot.setAttribute("cy", cy.toFixed(1));
}

function renderSubscores(sub) {
  const container = document.getElementById("subscores");
  container.innerHTML = "";
  const labels = {
    monetary_score: "Monetary (spend)",
    frequency_score: "Purchase frequency",
    recency_score: "Recency",
    tenure_score: "Tenure",
    engagement_score: "Engagement",
  };
  Object.entries(labels).forEach(([key, label]) => {
    const val = sub[key] ?? 0;
    const row = document.createElement("div");
    row.className = "subscore-row";
    row.innerHTML = `
      <div class="subscore-top"><span>${label}</span><span>${Math.round(val * 100)}%</span></div>
      <div class="subscore-track"><div class="subscore-fill" style="width:0%"></div></div>
    `;
    container.appendChild(row);
    requestAnimationFrame(() => {
      requestAnimationFrame(() => {
        row.querySelector(".subscore-fill").style.width = `${val * 100}%`;
      });
    });
  });
}

function renderResult(data) {
  resultEmpty.hidden = true;
  resultContent.hidden = false;

  document.getElementById("scoreValue").textContent = "0";
  animateNumber(document.getElementById("scoreValue"), data.loyalty_score);

  document.getElementById("segmentName").textContent = data.segment;
  document.getElementById("segmentName").style.color = data.color;
  document.getElementById("segmentHeadline").textContent = data.headline;

  const pill = document.getElementById("loyalPill");
  pill.textContent = data.is_loyal ? "Loyal Customer" : "Not Yet Loyal";
  pill.className = "loyal-pill " + (data.is_loyal ? "yes" : "no");

  document.getElementById("offerDiscount").textContent =
    `${data.discount_percent}%`;
  document.getElementById("offerName").textContent = data.offer;

  const perkList = document.getElementById("perkList");
  perkList.innerHTML = "";
  data.perks.forEach((p) => {
    const li = document.createElement("li");
    li.textContent = p;
    perkList.appendChild(li);
  });

  document.getElementById("customerDot").style.fill = data.color;
  placeDot(data.cluster, data.loyalty_score);

  renderSubscores(data.sub_scores);
}

form.addEventListener("submit", async (e) => {
  e.preventDefault();
  submitBtn.disabled = true;
  submitBtn.querySelector("span").textContent = "Analyzing…";

  try {
    const formData = new FormData(form);
    const payload = buildPayload(formData);

    const res = await fetch("/api/predict", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });

    if (!res.ok) throw new Error(`Request failed: ${res.status}`);
    const data = await res.json();
    renderResult(data);
  } catch (err) {
    console.error(err);
    alert(
      "Something went wrong while analyzing this customer. Check the console for details.",
    );
  } finally {
    submitBtn.disabled = false;
    submitBtn.querySelector("span").textContent = "Analyze Customer";
  }
});
