(() => {
  let catalog = window.INNOVA_CATALOG || { products: [], whatsappUrl: "https://wa.link/xdirph" };
  let products = catalog.products || [];
  let settings = {};

  const categoryList = document.querySelector("#category-list");
  const filterList = document.querySelector("#filter-list");
  const productList = document.querySelector("#product-list");
  const featuredList = document.querySelector("#featured-list");
  const searchInput = document.querySelector("#product-search");
  const sortSelect = document.querySelector("#sort-order");
  const resultCount = document.querySelector("#result-count");
  const emptyState = document.querySelector("#empty-state");
  const dialog = document.querySelector("#product-dialog");
  const dialogContent = document.querySelector("#dialog-content");
  const toast = document.querySelector("#toast");

  // Account Modal elements
  const accountDialog = document.querySelector("#account-dialog");
  const accountDialogClose = document.querySelector("#account-dialog-close");
  const navAccountBtn = document.querySelector("#nav-account-btn");
  const headerNotifPill = document.querySelector("#header-notif-pill");
  const accountAuthContainer = document.querySelector("#account-auth-container");
  const accountPortalContainer = document.querySelector("#account-portal-container");

  let categories = [];
  const state = {
    category: "Todos",
    search: "",
    sort: "featured",
    user: null,
    favorites: new Set(),
    notifications: [],
    activity: [],
    recommendations: []
  };
  let toastTimeout;
  let searchTrackTimeout;

  const formatPrice = (price) => {
    const symbol = settings.currency_symbol || "$";
    const formatted = new Intl.NumberFormat("es-CO", {
      maximumFractionDigits: 0
    }).format(price || 0);
    return `${symbol} ${formatted}`;
  };

  const getProductImage = (product) => {
    return product.primary_image || product.image || (product.images && product.images[0] ? product.images[0].image_url : "assets/innova-mark.png");
  };

  const imageMarkup = (product, className = "") => `
    <img class="${className}" src="${getProductImage(product)}" alt="${product.name}" loading="lazy" decoding="async">
  `;

  const productCard = (product) => {
    const isSoldOut = product.stock_status === "out_of_stock" || product.stock <= 0;
    const isLowStock = product.stock_status === "low_stock";
    const hasDiscount = Boolean(product.has_discount);
    const displayPrice = hasDiscount ? product.effective_price : product.price;
    const isFav = state.favorites.has(product.id);

    return `
      <article class="product-card ${isSoldOut ? "product-card-soldout" : ""}" data-product-card="${product.id}">
        <button class="btn-favorite ${isFav ? "is-favorite" : ""}" type="button" data-favorite="${product.id}" aria-label="${isFav ? "Quitar de favoritos" : "Añadir a favoritos"}" title="${isFav ? "Quitar de favoritos" : "Guardar en favoritos"}">
          ${isFav ? "❤️" : "♡"}
        </button>
        <button class="product-image-wrap" type="button" data-details="${product.id}" aria-label="Ver detalles de ${product.name}">
          ${imageMarkup(product)}
          <div class="product-badges">
            ${product.featured ? '<span class="product-badge">Destacado</span>' : ""}
            ${hasDiscount ? `<span class="product-badge product-badge-discount">-${product.discount_percent}%</span>` : ""}
            ${isSoldOut ? '<span class="product-badge product-badge-soldout">Agotado</span>' : ""}
          </div>
        </button>
        <div class="product-details">
          <span class="product-category">${product.category_name || product.category || "General"}</span>
          <div class="product-topline">
            <h4 class="product-name">${product.name}</h4>
            <div class="product-price-wrap">
              ${hasDiscount ? `<span class="product-price-old">${formatPrice(product.price)}</span>` : ""}
              <span class="product-price product-price-current">${formatPrice(displayPrice)}</span>
              ${isLowStock ? '<span class="stock-warning-label">Pocas unidades</span>' : ""}
              ${isSoldOut ? '<span class="stock-out-label">Agotado</span>' : ""}
            </div>
          </div>
          <p class="product-description">${product.short_description || product.description || ""}</p>
          <div class="product-actions">
            <button class="detail-link" type="button" data-details="${product.id}">Ver detalles</button>
            <button class="inquiry-link" type="button" data-inquiry="${product.id}" ${isSoldOut ? 'data-soldout="true"' : ""}>
              ${isSoldOut ? "Consultar llegada" : "Consultar"} <span aria-hidden="true">↗</span>
            </button>
          </div>
        </div>
      </article>
    `;
  };

  function updateCategories() {
    categories = [...new Set(products.map((p) => p.category_name || p.category || "General"))];
  }

  function renderCategories() {
    updateCategories();
    categoryList.innerHTML = categories.map((category) => {
      const product = products.find((item) => (item.category_name || item.category) === category);
      const count = products.filter((item) => (item.category_name || item.category) === category).length;
      return `
        <button class="category-card" type="button" data-category="${category}" aria-label="Ver ${category}, ${count} productos">
          ${product ? imageMarkup(product) : ""}
          <span>${category}</span>
          <small>${String(count).padStart(2, "0")} productos <span aria-hidden="true">↗</span></small>
        </button>
      `;
    }).join("");

    filterList.innerHTML = ["Todos", ...categories].map((category) => `
      <button class="filter-chip" type="button" data-filter="${category}" aria-pressed="${category === state.category}">
        ${category}
      </button>
    `).join("");
  }

  function renderFeatured() {
    const featuredItems = products.filter((p) => p.featured);
    featuredList.innerHTML = featuredItems.map((product) => {
      const hasDiscount = Boolean(product.has_discount);
      const displayPrice = hasDiscount ? product.effective_price : product.price;
      const isSoldOut = product.stock_status === "out_of_stock" || product.stock <= 0;

      return `
        <button class="featured-card ${isSoldOut ? "product-card-soldout" : ""}" type="button" data-details="${product.id}" aria-label="Ver detalles de ${product.name}">
          ${imageMarkup(product)}
          <span class="featured-copy">
            <small>${product.category_name || product.category || "General"}</small>
            <strong>${product.name}</strong>
            <span>${hasDiscount ? `<del style="color:#777;font-size:10px">${formatPrice(product.price)}</del> ` : ""}${formatPrice(displayPrice)}${isSoldOut ? " · (Agotado)" : ""}</span>
          </span>
        </button>
      `;
    }).join("");
  }

  function getVisibleProducts() {
    const normalizedSearch = state.search.trim().toLocaleLowerCase("es");
    const matching = products.filter((product) => {
      const cat = product.category_name || product.category || "General";
      const matchesCategory = state.category === "Todos" || cat === state.category;
      const matchesSearch = !normalizedSearch || product.name.toLocaleLowerCase("es").includes(normalizedSearch);
      return matchesCategory && matchesSearch;
    });

    if (state.sort === "price-asc") {
      return matching.sort((a, b) => (a.effective_price || a.price) - (b.effective_price || b.price));
    }
    if (state.sort === "price-desc") {
      return matching.sort((a, b) => (b.effective_price || b.price) - (a.effective_price || a.price));
    }
    return matching.sort((a, b) => Number(b.featured) - Number(a.featured));
  }

  function renderProducts() {
    const visibleProducts = getVisibleProducts();
    productList.innerHTML = visibleProducts.map(productCard).join("");
    productList.hidden = visibleProducts.length === 0;
    emptyState.hidden = visibleProducts.length !== 0;
    resultCount.textContent = `${visibleProducts.length} ${visibleProducts.length === 1 ? "producto" : "productos"}`;
    filterList.querySelectorAll("[data-filter]").forEach((button) => {
      button.setAttribute("aria-pressed", String(button.dataset.filter === state.category));
    });
  }

  function updateFavoriteHeartIcons() {
    document.querySelectorAll("[data-favorite]").forEach((btn) => {
      const pid = btn.dataset.favorite;
      const isFav = state.favorites.has(pid);
      btn.classList.toggle("is-favorite", isFav);
      btn.innerHTML = isFav ? "❤️" : "♡";
      btn.setAttribute("aria-label", isFav ? "Quitar de favoritos" : "Añadir a favoritos");
      btn.setAttribute("title", isFav ? "Quitar de favoritos" : "Guardar en favoritos");
    });
  }

  function showToast(message) {
    window.clearTimeout(toastTimeout);
    toast.textContent = message;
    toast.classList.add("is-visible");
    toastTimeout = window.setTimeout(() => toast.classList.remove("is-visible"), 3600);
  }

  function contactByWhatsApp(product) {
    const whatsappUrl = settings.whatsapp_url || catalog.whatsappUrl;
    if (!whatsappUrl) {
      showToast("WhatsApp aún no está configurado.");
      return;
    }

    let url = whatsappUrl;
    if (product) {
      const hasDiscount = Boolean(product.has_discount);
      const displayPrice = hasDiscount ? product.effective_price : product.price;
      const isSoldOut = product.stock_status === "out_of_stock" || product.stock <= 0;
      const statusNote = isSoldOut ? " [Actualmente agotado - Deseo consultar fecha de reposición]" : "";
      const text = `Hola INNOVA, estoy interesado en el producto: ${product.name} (Ref: ${product.sku || product.id}) - Precio: ${formatPrice(displayPrice)}${statusNote}`;
      
      const separator = url.includes("?") ? "&" : "?";
      url = `${url}${separator}text=${encodeURIComponent(text)}`;
    }

    window.open(url, "_blank", "noopener,noreferrer");
  }

  function openProductDetails(id) {
    const product = products.find((item) => item.id === id);
    if (!product) {
      showToast("No pudimos encontrar los detalles de ese producto.");
      return;
    }

    // Log activity: view_product
    logCustomerActivity("view_product", { product_id: product.id });

    const hasDiscount = Boolean(product.has_discount);
    const displayPrice = hasDiscount ? product.effective_price : product.price;
    const isSoldOut = product.stock_status === "out_of_stock" || product.stock <= 0;
    const isLowStock = product.stock_status === "low_stock";
    const specs = Array.isArray(product.specs) ? product.specs : [];
    const isFav = state.favorites.has(product.id);

    dialogContent.innerHTML = `
      <div class="dialog-product ${isSoldOut ? "product-card-soldout" : ""}">
        <div style="position:relative; width:100%; height:100%;">
          ${imageMarkup(product)}
          <button class="btn-favorite ${isFav ? "is-favorite" : ""}" type="button" data-favorite="${product.id}" aria-label="${isFav ? "Quitar de favoritos" : "Añadir a favoritos"}" style="top:14px; right:14px;">
            ${isFav ? "❤️" : "♡"}
          </button>
        </div>
        <div class="dialog-copy">
          <span class="product-category">${product.category_name || product.category || "General"}</span>
          <h2 id="dialog-title">${product.name}</h2>
          <div style="margin: 0 0 16px;">
            ${hasDiscount ? `<span style="font-size:12px; color:#888; text-decoration:line-through;">${formatPrice(product.price)}</span> ` : ""}
            <span class="dialog-price" style="margin:0; font-size:18px; font-weight:700;">${formatPrice(displayPrice)}</span>
            ${hasDiscount ? `<span style="display:inline-block; margin-left:8px; padding:2px 6px; background:#fff; color:#000; font-size:10px; font-weight:700;">-${product.discount_percent}%</span>` : ""}
            ${isLowStock ? '<p style="color:#f59e0b; font-size:10px; margin:4px 0 0;">⚠️ Pocas unidades disponibles en inventario</p>' : ""}
            ${isSoldOut ? '<p style="color:#ef4444; font-size:11px; font-weight:700; margin:4px 0 0;">🚫 Este producto se encuentra actualmente agotado</p>' : ""}
          </div>
          <p class="dialog-description">${product.full_description || product.details || product.short_description || product.description || ""}</p>
          ${specs.length > 0 ? `<ul class="dialog-specs">${specs.map((s) => `<li>${s}</li>`).join("")}</ul>` : ""}
          <div style="display:flex; gap:10px; flex-wrap:wrap; width:100%;">
            <button class="button button-dark" type="button" data-inquiry="${product.id}" style="flex:1;">
              ${isSoldOut ? "Consultar disponibilidad" : "Consultar producto por WhatsApp"} <span aria-hidden="true">↗</span>
            </button>
            <button class="button button-light btn-sm" type="button" data-favorite="${product.id}" style="height:auto; padding:0 14px;">
              ${isFav ? "❤️ Guardado en Favoritos" : "♡ Guardar en Favoritos"}
            </button>
          </div>
        </div>
      </div>
    `;
    dialog.showModal();
  }

  // ========================================================
  // CUSTOMER AUTH & ACTIVITY SYSTEM
  // ========================================================
  function logCustomerActivity(eventType, details = {}) {
    try {
      fetch("/api/customer/activity", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ event_type: eventType, ...details })
      }).catch(() => {});
    } catch (e) {}
  }

  async function checkAuthSession() {
    try {
      const res = await fetch("/api/auth/me", { cache: "no-store" });
      if (res.ok) {
        const data = await res.json();
        if (data.authenticated && data.user) {
          setLoggedInCustomer(data.user);
          return;
        }
      }
    } catch (err) {
      console.debug("Session check error:", err);
    }
    setLoggedOutCustomer();
  }

  function setLoggedInCustomer(user) {
    state.user = user;
    
    // Update Header Account button
    const label = document.querySelector("#nav-account-label");
    if (label) {
      const displayName = user.full_name ? user.full_name.split(" ")[0] : (user.username || "Mi Cuenta");
      label.textContent = displayName;
    }

    // Update portal header info
    document.querySelector("#portal-user-name").textContent = user.full_name || user.username || "Cliente";
    document.querySelector("#portal-user-email").textContent = user.email || "";
    document.querySelector("#portal-user-role").textContent = user.role === "admin" ? "Administrador" : "Cliente";
    document.querySelector("#portal-user-initial").textContent = (user.full_name || user.username || "C")[0].toUpperCase();

    // Show/hide Admin Link
    const adminLink = document.querySelector("#portal-admin-link");
    if (adminLink) {
      adminLink.hidden = user.role !== "admin";
    }

    // Populate profile inputs
    const pName = document.querySelector("#portal-input-name");
    const pPhone = document.querySelector("#portal-input-phone");
    const pEmail = document.querySelector("#portal-static-email");
    const pDate = document.querySelector("#portal-static-date");

    if (pName) pName.value = user.full_name || "";
    if (pPhone) pPhone.value = user.phone || "";
    if (pEmail) pEmail.value = user.email || "";
    if (pDate) pDate.textContent = user.created_at ? new Date(user.created_at).toLocaleDateString("es-CO", { year: "numeric", month: "long", day: "numeric" }) : "-";

    // Set notification preferences checkboxes
    const prefs = user.notification_prefs || { promos: true, new_products: true, stock_alerts: true };
    const prefPromos = document.querySelector("#portal-pref-promos");
    const prefNew = document.querySelector("#portal-pref-new");
    const prefStock = document.querySelector("#portal-pref-stock");
    if (prefPromos) prefPromos.checked = Boolean(prefs.promos);
    if (prefNew) prefNew.checked = Boolean(prefs.new_products);
    if (prefStock) prefStock.checked = Boolean(prefs.stock_alerts);

    // Load customer data
    loadCustomerFavorites();
    loadCustomerNotifications();
    loadCustomerRecommendations();
  }

  function setLoggedOutCustomer() {
    state.user = null;
    state.favorites.clear();
    state.notifications = [];
    state.recommendations = [];

    const label = document.querySelector("#nav-account-label");
    if (label) label.textContent = "Mi Cuenta";

    if (headerNotifPill) headerNotifPill.hidden = true;
    updateFavoriteHeartIcons();
  }

  async function loadCustomerFavorites() {
    if (!state.user) return;
    try {
      const res = await fetch("/api/customer/favorites", { cache: "no-store" });
      if (!res.ok) return;
      const data = await res.json();
      const favs = data.favorites || [];
      state.favorites = new Set(favs.map((f) => f.product_id));

      const favCountElem = document.querySelector("#portal-favs-count");
      if (favCountElem) favCountElem.textContent = state.favorites.size;

      renderPortalFavorites(favs);
      updateFavoriteHeartIcons();
    } catch (err) {
      console.warn("Error loading favorites:", err);
    }
  }

  function renderPortalFavorites(favs) {
    const grid = document.querySelector("#portal-favs-grid");
    const empty = document.querySelector("#portal-favs-empty");
    if (!grid || !empty) return;

    if (favs.length === 0) {
      grid.innerHTML = "";
      empty.hidden = false;
      return;
    }

    empty.hidden = true;
    grid.innerHTML = favs.map((f) => {
      const hasDiscount = Boolean(f.has_discount);
      const displayPrice = hasDiscount ? f.effective_price : f.price;
      const isSoldOut = f.stock <= 0;

      return `
        <div class="portal-card">
          <img src="${f.primary_image || f.image || 'assets/innova-mark.png'}" alt="${f.name}">
          <div class="portal-card-body">
            <strong>${f.name}</strong>
            <small style="color:var(--muted);">${f.category_name || "General"}</small>
            <span style="font-size:12px; font-weight:700; margin-top:4px;">${formatPrice(displayPrice)}</span>
            <div class="portal-card-actions">
              <button class="button button-light btn-sm" type="button" data-details="${f.product_id}">Ver</button>
              <button class="button button-dark btn-sm" type="button" data-favorite="${f.product_id}" style="color:#ef4444; border-color:#ef4444;">Quitar</button>
            </div>
          </div>
        </div>
      `;
    }).join("");
  }

  async function loadCustomerNotifications() {
    if (!state.user) return;
    try {
      const res = await fetch("/api/customer/notifications", { cache: "no-store" });
      if (!res.ok) return;
      const data = await res.json();
      state.notifications = data.notifications || [];
      
      const unreadCount = data.unread_count || 0;
      if (headerNotifPill) {
        headerNotifPill.textContent = unreadCount;
        headerNotifPill.hidden = unreadCount <= 0;
      }

      const notifCountElem = document.querySelector("#portal-notifs-count");
      if (notifCountElem) notifCountElem.textContent = unreadCount;

      renderPortalNotifications(state.notifications);
    } catch (err) {
      console.warn("Error loading notifications:", err);
    }
  }

  function renderPortalNotifications(notifs) {
    const list = document.querySelector("#portal-notifs-list");
    const empty = document.querySelector("#portal-notifs-empty");
    if (!list || !empty) return;

    if (notifs.length === 0) {
      list.innerHTML = "";
      empty.hidden = false;
      return;
    }

    empty.hidden = true;
    list.innerHTML = notifs.map((n) => {
      const isUnread = Number(n.is_read) === 0;
      const timeStr = n.created_at ? new Date(n.created_at).toLocaleString("es-CO", { dateStyle: "short", timeStyle: "short" }) : "";

      return `
        <div class="notif-card ${isUnread ? "is-unread" : ""}" data-notif-card="${n.id}">
          <div style="flex:1;">
            <h5>${n.title} ${isUnread ? '<span style="display:inline-block; width:6px; height:6px; border-radius:50%; background:#fff; margin-left:4px; vertical-align:middle;"></span>' : ""}</h5>
            <p>${n.message}</p>
            <span class="notif-time">${timeStr}</span>
          </div>
          <div class="notif-actions">
            ${isUnread ? `<button type="button" class="link-btn" data-mark-read="${n.id}">Marcar leída</button>` : ""}
            <button type="button" class="btn-icon" data-delete-notif="${n.id}" title="Eliminar notificación" style="color:#777; font-size:12px;">✕</button>
          </div>
        </div>
      `;
    }).join("");
  }

  async function loadCustomerRecommendations() {
    if (!state.user) return;
    try {
      const res = await fetch("/api/customer/recommendations", { cache: "no-store" });
      if (!res.ok) return;
      const data = await res.json();
      state.recommendations = data.recommendations || [];
      renderPortalRecommendations(state.recommendations, data.type);
    } catch (err) {
      console.warn("Error loading recommendations:", err);
    }
  }

  function renderPortalRecommendations(recs, type) {
    const grid = document.querySelector("#portal-recs-grid");
    const sub = document.querySelector("#portal-recs-sub");
    if (!grid) return;

    if (sub) {
      sub.textContent = type === "personalized" 
        ? "Selección exclusiva basada en tu historial de consultas, categorías preferidas y ofertas vigentes con stock disponible."
        : "Nuestras piezas más valoradas y con disponibilidad inmediata para comenzar a descubrir INNOVA.";
    }

    if (recs.length === 0) {
      grid.innerHTML = `<div class="portal-empty-state"><p>No hay recomendaciones activas en este momento.</p></div>`;
      return;
    }

    grid.innerHTML = recs.map((r) => {
      const hasDiscount = Boolean(r.has_discount);
      const displayPrice = hasDiscount ? r.effective_price : r.price;

      return `
        <div class="portal-card">
          <img src="${r.primary_image || r.image || 'assets/innova-mark.png'}" alt="${r.name}">
          <div class="portal-card-body">
            <span class="rec-reason-badge">${r.recommendation_reason || "Recomendado"}</span>
            <strong>${r.name}</strong>
            <small style="color:var(--muted);">${r.category_name || "General"}</small>
            <span style="font-size:12px; font-weight:700; margin-top:4px;">${formatPrice(displayPrice)}</span>
            <div class="portal-card-actions">
              <button class="button button-light btn-sm" type="button" data-details="${r.id}">Ver</button>
              <button class="button button-dark btn-sm" type="button" data-inquiry="${r.id}">Consultar ↗</button>
            </div>
          </div>
        </div>
      `;
    }).join("");
  }

  async function loadCustomerActivity() {
    if (!state.user) return;
    try {
      const res = await fetch("/api/customer/activity", { cache: "no-store" });
      if (!res.ok) return;
      const data = await res.json();
      const list = document.querySelector("#portal-activity-list");
      const empty = document.querySelector("#portal-activity-empty");
      if (!list || !empty) return;

      const items = data.activity || [];
      if (items.length === 0) {
        list.innerHTML = "";
        empty.hidden = false;
        return;
      }

      empty.hidden = true;
      list.innerHTML = items.map((act) => {
        const timeStr = act.created_at ? new Date(act.created_at).toLocaleString("es-CO", { dateStyle: "short", timeStyle: "short" }) : "";
        let desc = "Interacción con la tienda";
        if (act.event_type === "view_product") desc = `Consulta de producto: <strong>${act.product_name || act.product_id}</strong>`;
        else if (act.event_type === "search") desc = `Búsqueda en catálogo: <em>"${act.search_query}"</em>`;
        else if (act.event_type === "view_category") desc = `Exploración de categoría: <strong>${act.category_name}</strong>`;
        else if (act.event_type === "add_favorite") desc = `Agregado a favoritos: <strong>${act.product_name || act.product_id}</strong>`;

        return `
          <div class="activity-item">
            <div>${desc}</div>
            <small>${timeStr}</small>
          </div>
        `;
      }).join("");
    } catch (err) {
      console.warn("Error loading activity:", err);
    }
  }

  async function toggleFavorite(productId) {
    if (!state.user) {
      showToast("Inicia sesión para guardar tus productos favoritos");
      openAccountModal("login");
      return;
    }

    try {
      const res = await fetch("/api/customer/favorites/toggle", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ product_id: productId })
      });
      const data = await res.json();
      if (res.ok && data.success) {
        if (data.action === "added") {
          state.favorites.add(productId);
          showToast("Producto agregado a tus favoritos ❤️");
        } else {
          state.favorites.delete(productId);
          showToast("Producto quitado de tus favoritos");
        }

        updateFavoriteHeartIcons();
        const favCountElem = document.querySelector("#portal-favs-count");
        if (favCountElem) favCountElem.textContent = state.favorites.size;

        // Reload favorites list & recommendations
        loadCustomerFavorites();
        loadCustomerRecommendations();
      } else {
        showToast(data.error || "No se pudo actualizar favoritos");
      }
    } catch (err) {
      showToast("Error de conexión al guardar favorito");
    }
  }

  // ========================================================
  // ACCOUNT MODAL & PORTAL CONTROLS
  // ========================================================
  function openAccountModal(view = "portal") {
    if (state.user) {
      accountAuthContainer.hidden = true;
      accountPortalContainer.hidden = false;
      switchPortalTab("recs");
    } else {
      accountAuthContainer.hidden = false;
      accountPortalContainer.hidden = true;
      switchAuthTab(view === "register" ? "register" : "login");
    }
    accountDialog.showModal();
  }

  function switchAuthTab(tabName) {
    document.querySelectorAll(".auth-tab-btn").forEach((btn) => {
      btn.classList.toggle("active", btn.dataset.authTab === tabName);
    });
    document.querySelectorAll(".auth-panel").forEach((panel) => {
      panel.hidden = true;
      panel.classList.remove("active");
    });

    const target = document.querySelector(`#auth-panel-${tabName}`);
    if (target) {
      target.hidden = false;
      target.classList.add("active");
    }
  }

  function switchPortalTab(tabName) {
    document.querySelectorAll(".portal-tab-btn").forEach((btn) => {
      btn.classList.toggle("active", btn.dataset.portalTab === tabName);
    });
    document.querySelectorAll(".portal-panel").forEach((panel) => {
      panel.hidden = true;
      panel.classList.remove("active");
    });

    const target = document.querySelector(`#portal-panel-${tabName}`);
    if (target) {
      target.hidden = false;
      target.classList.add("active");
    }

    if (tabName === "activity") loadCustomerActivity();
    else if (tabName === "favs") loadCustomerFavorites();
    else if (tabName === "notifs") loadCustomerNotifications();
    else if (tabName === "recs") loadCustomerRecommendations();
  }

  // Hook navigation account button
  navAccountBtn.addEventListener("click", () => openAccountModal());
  accountDialogClose.addEventListener("click", () => accountDialog.close());
  accountDialog.addEventListener("click", (event) => {
    if (event.target === accountDialog) accountDialog.close();
  });

  // Auth Tabs navigation
  document.querySelectorAll("[data-auth-tab]").forEach((btn) => {
    btn.addEventListener("click", () => switchAuthTab(btn.dataset.authTab));
  });

  // Show / Hide forgot password
  document.querySelector("#btn-show-forgot").addEventListener("click", () => switchAuthTab("forgot"));
  document.querySelector("#btn-back-to-login").addEventListener("click", () => switchAuthTab("login"));

  // Toggle eye on login password
  document.querySelector("#toggle-cust-password").addEventListener("click", () => {
    const input = document.querySelector("#cust-login-password");
    if (input.type === "password") {
      input.type = "text";
      document.querySelector("#toggle-cust-password").textContent = "🙈";
    } else {
      input.type = "password";
      document.querySelector("#toggle-cust-password").textContent = "👁️";
    }
  });

  // Portal tabs navigation
  document.querySelectorAll("[data-portal-tab]").forEach((btn) => {
    btn.addEventListener("click", () => switchPortalTab(btn.dataset.portalTab));
  });

  // Customer Login Handler
  const customerLoginForm = document.querySelector("#customer-login-form");
  customerLoginForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    const errorBox = document.querySelector("#customer-login-error");
    errorBox.hidden = true;

    const identifier = document.querySelector("#cust-login-identifier").value.trim();
    const password = document.querySelector("#cust-login-password").value;
    const submitBtn = document.querySelector("#btn-cust-login-submit");

    if (!identifier || !password) {
      errorBox.textContent = "Por favor ingresa tu identificador y contraseña.";
      errorBox.hidden = false;
      return;
    }

    submitBtn.disabled = true;
    submitBtn.textContent = "Verificando...";

    try {
      const res = await fetch("/api/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ identifier, password })
      });
      const data = await res.json();

      if (res.ok && data.success) {
        if (data.user.role === "admin") {
          // Administrator routing
          window.location.href = "/admin";
          return;
        }

        // Client routing
        setLoggedInCustomer(data.user);
        accountAuthContainer.hidden = true;
        accountPortalContainer.hidden = false;
        switchPortalTab("recs");
        showToast(`¡Bienvenido, ${data.user.full_name || data.user.username}!`);
      } else {
        errorBox.textContent = data.error || "Credenciales incorrectas.";
        errorBox.hidden = false;
      }
    } catch (err) {
      errorBox.textContent = "Error al conectar con el servidor.";
      errorBox.hidden = false;
    } finally {
      submitBtn.disabled = false;
      submitBtn.textContent = "Iniciar Sesión";
    }
  });

  // Customer Register Handler
  const customerRegisterForm = document.querySelector("#customer-register-form");
  customerRegisterForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    const errorBox = document.querySelector("#customer-register-error");
    errorBox.hidden = true;

    const full_name = document.querySelector("#cust-reg-name").value.trim();
    const email = document.querySelector("#cust-reg-email").value.trim();
    const password = document.querySelector("#cust-reg-password").value;
    const confirm = document.querySelector("#cust-reg-confirm").value;

    if (!full_name || !email || !password) {
      errorBox.textContent = "Por favor completa todos los campos requeridos.";
      errorBox.hidden = false;
      return;
    }

    if (password !== confirm) {
      errorBox.textContent = "Las contraseñas no coinciden.";
      errorBox.hidden = false;
      return;
    }

    if (password.length < 8) {
      errorBox.textContent = "La contraseña debe tener al menos 8 caracteres.";
      errorBox.hidden = false;
      return;
    }

    const notification_prefs = {
      promos: document.querySelector("#reg-pref-promos").checked,
      new_products: document.querySelector("#reg-pref-new").checked,
      stock_alerts: document.querySelector("#reg-pref-stock").checked
    };

    const submitBtn = document.querySelector("#btn-cust-register-submit");
    submitBtn.disabled = true;
    submitBtn.textContent = "Creando cuenta...";

    try {
      const res = await fetch("/api/auth/register", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password, full_name, notification_prefs })
      });
      const data = await res.json();

      if (res.ok && data.success) {
        setLoggedInCustomer(data.user);
        accountAuthContainer.hidden = true;
        accountPortalContainer.hidden = false;
        switchPortalTab("recs");
        showToast("¡Cuenta creada exitosamente! Bienvenido a INNOVA.");
      } else {
        errorBox.textContent = data.error || "No se pudo registrar la cuenta.";
        errorBox.hidden = false;
      }
    } catch (err) {
      errorBox.textContent = "Error al conectar con el servidor.";
      errorBox.hidden = false;
    } finally {
      submitBtn.disabled = false;
      submitBtn.textContent = "Registrarme e Iniciar Sesión";
    }
  });

  // Password Reset Flow
  document.querySelector("#btn-send-reset-code").addEventListener("click", async () => {
    const email = document.querySelector("#cust-forgot-email").value.trim();
    const msgBox = document.querySelector("#customer-forgot-msg");
    msgBox.hidden = true;

    if (!email) {
      msgBox.className = "dialog-alert dialog-alert-error";
      msgBox.textContent = "Por favor ingresa tu correo electrónico.";
      msgBox.hidden = false;
      return;
    }

    try {
      const res = await fetch("/api/auth/password-reset/request", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email })
      });
      const data = await res.json();
      if (res.ok && data.success) {
        msgBox.className = "dialog-alert dialog-alert-success";
        msgBox.textContent = data.message || "Código generado. Ingrésalo a continuación.";
        msgBox.hidden = false;
        document.querySelector("#forgot-step-2").hidden = false;
        if (data.token) {
          document.querySelector("#cust-reset-token").value = data.token;
        }
      } else {
        msgBox.className = "dialog-alert dialog-alert-error";
        msgBox.textContent = data.error || "Error al procesar la solicitud.";
        msgBox.hidden = false;
      }
    } catch (err) {
      msgBox.className = "dialog-alert dialog-alert-error";
      msgBox.textContent = "Error de conexión con el servidor.";
      msgBox.hidden = false;
    }
  });

  document.querySelector("#btn-confirm-reset-pass").addEventListener("click", async () => {
    const token = document.querySelector("#cust-reset-token").value.trim();
    const new_password = document.querySelector("#cust-reset-newpass").value;
    const msgBox = document.querySelector("#customer-forgot-msg");

    if (!token || !new_password || new_password.length < 8) {
      msgBox.className = "dialog-alert dialog-alert-error";
      msgBox.textContent = "Ingresa el código y una nueva contraseña de al menos 8 caracteres.";
      msgBox.hidden = false;
      return;
    }

    try {
      const res = await fetch("/api/auth/password-reset/confirm", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ token, new_password })
      });
      const data = await res.json();
      if (res.ok && data.success) {
        showToast("Contraseña restablecida exitosamente. Inicia sesión.");
        switchAuthTab("login");
      } else {
        msgBox.className = "dialog-alert dialog-alert-error";
        msgBox.textContent = data.error || "Código inválido o expirado.";
        msgBox.hidden = false;
      }
    } catch (err) {
      msgBox.className = "dialog-alert dialog-alert-error";
      msgBox.textContent = "Error al restablecer la contraseña.";
      msgBox.hidden = false;
    }
  });

  // Portal Logout Handler
  document.querySelector("#btn-portal-logout").addEventListener("click", async () => {
    try {
      await fetch("/api/auth/logout", { method: "POST" });
    } finally {
      setLoggedOutCustomer();
      accountDialog.close();
      showToast("Has cerrado tu sesión.");
    }
  });

  // Portal Notifications: Mark All Read
  document.querySelector("#btn-mark-all-read").addEventListener("click", async () => {
    try {
      const res = await fetch("/api/customer/notifications/read-all", { method: "PUT" });
      if (res.ok) {
        showToast("Todas las notificaciones marcadas como leídas.");
        loadCustomerNotifications();
      }
    } catch (err) {
      showToast("Error al actualizar notificaciones.");
    }
  });

  // Portal Notifications: Save Preferences
  document.querySelector("#btn-save-notif-prefs").addEventListener("click", async () => {
    const prefs = {
      promos: document.querySelector("#portal-pref-promos").checked,
      new_products: document.querySelector("#portal-pref-new").checked,
      stock_alerts: document.querySelector("#portal-pref-stock").checked
    };

    try {
      const res = await fetch("/api/customer/profile", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ notification_prefs: prefs })
      });
      const data = await res.json();
      if (res.ok && data.success) {
        showToast("Preferencias de notificación guardadas.");
        if (state.user) state.user.notification_prefs = prefs;
      } else {
        showToast(data.error || "No se pudieron guardar las preferencias");
      }
    } catch (err) {
      showToast("Error de conexión al guardar preferencias");
    }
  });

  // Portal Activity: Clear
  document.querySelector("#btn-clear-activity").addEventListener("click", async () => {
    if (!confirm("¿Deseas borrar tu historial de actividad registrado?")) return;
    try {
      const res = await fetch("/api/customer/activity", { method: "DELETE" });
      if (res.ok) {
        showToast("Historial de actividad borrado correctamente.");
        loadCustomerActivity();
      }
    } catch (err) {
      showToast("Error al borrar historial.");
    }
  });

  // Portal Profile: Update Info
  document.querySelector("#portal-profile-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const full_name = document.querySelector("#portal-input-name").value.trim();
    const phone = document.querySelector("#portal-input-phone").value.trim();

    try {
      const res = await fetch("/api/customer/profile", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ full_name, phone })
      });
      const data = await res.json();
      if (res.ok && data.success) {
        showToast("Datos de perfil actualizados exitosamente.");
        if (state.user) {
          state.user.full_name = full_name;
          state.user.phone = phone;
          setLoggedInCustomer(state.user);
        }
      } else {
        showToast(data.error || "Error al actualizar perfil");
      }
    } catch (err) {
      showToast("Error de red al actualizar perfil");
    }
  });

  // Portal Profile: Change Password
  document.querySelector("#portal-change-pass-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const msgBox = document.querySelector("#portal-pass-msg");
    msgBox.hidden = true;

    const current_password = document.querySelector("#portal-pass-curr").value;
    const new_password = document.querySelector("#portal-pass-new").value;

    if (!current_password || !new_password || new_password.length < 8) {
      msgBox.className = "dialog-alert dialog-alert-error";
      msgBox.textContent = "La nueva contraseña debe tener al menos 8 caracteres.";
      msgBox.hidden = false;
      return;
    }

    try {
      const res = await fetch("/api/customer/change-password", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ current_password, new_password })
      });
      const data = await res.json();
      if (res.ok && data.success) {
        msgBox.className = "dialog-alert dialog-alert-success";
        msgBox.textContent = "Contraseña actualizada exitosamente.";
        msgBox.hidden = false;
        document.querySelector("#portal-pass-curr").value = "";
        document.querySelector("#portal-pass-new").value = "";
      } else {
        msgBox.className = "dialog-alert dialog-alert-error";
        msgBox.textContent = data.error || "Contraseña actual incorrecta.";
        msgBox.hidden = false;
      }
    } catch (err) {
      msgBox.className = "dialog-alert dialog-alert-error";
      msgBox.textContent = "Error de red al cambiar contraseña.";
      msgBox.hidden = false;
    }
  });

  // Portal Profile: Delete Account (GDPR)
  document.querySelector("#btn-delete-account").addEventListener("click", async () => {
    const confirmation = prompt("Esta acción es irreversible. Todos tus datos personales, favoritos y actividad serán borrados de forma permanente.\n\nEscribe ELIMINAR para confirmar:");
    if (confirmation !== "ELIMINAR") return;

    try {
      const res = await fetch("/api/customer/account", { method: "DELETE" });
      const data = await res.json();
      if (res.ok && data.success) {
        setLoggedOutCustomer();
        accountDialog.close();
        showToast("Tu cuenta y datos han sido eliminados de acuerdo a la ley de privacidad.");
      } else {
        showToast(data.error || "No se pudo eliminar la cuenta.");
      }
    } catch (err) {
      showToast("Error de red al solicitar eliminación de cuenta.");
    }
  });

  // Notification Card Actions (Mark Read & Delete)
  document.querySelector("#portal-notifs-list").addEventListener("click", async (e) => {
    const markReadBtn = e.target.closest("[data-mark-read]");
    if (markReadBtn) {
      const nId = markReadBtn.dataset.markRead;
      try {
        const res = await fetch(`/api/customer/notifications/${nId}/read`, { method: "PUT" });
        if (res.ok) loadCustomerNotifications();
      } catch (err) {}
      return;
    }

    const delBtn = e.target.closest("[data-delete-notif]");
    if (delBtn) {
      const nId = delBtn.dataset.deleteNotif;
      try {
        const res = await fetch(`/api/customer/notifications/${nId}`, { method: "DELETE" });
        if (res.ok) {
          showToast("Notificación eliminada.");
          loadCustomerNotifications();
        }
      } catch (err) {}
      return;
    }
  });

  // ========================================================
  // CATALOG EVENT LISTENERS
  // ========================================================
  categoryList.addEventListener("click", (event) => {
    const button = event.target.closest("[data-category]");
    if (!button) return;
    state.category = button.dataset.category;
    logCustomerActivity("view_category", { category_name: state.category });
    renderProducts();
    document.querySelector("#catalogo").scrollIntoView({
      behavior: window.matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth"
    });
  });

  filterList.addEventListener("click", (event) => {
    const button = event.target.closest("[data-filter]");
    if (!button) return;
    state.category = button.dataset.filter;
    logCustomerActivity("view_category", { category_name: state.category });
    renderProducts();
  });

  searchInput.addEventListener("input", () => {
    state.search = searchInput.value;
    renderProducts();

    window.clearTimeout(searchTrackTimeout);
    if (state.search.trim().length >= 3) {
      searchTrackTimeout = window.setTimeout(() => {
        logCustomerActivity("search", { query: state.search.trim() });
      }, 1200);
    }
  });

  sortSelect.addEventListener("change", () => {
    state.sort = sortSelect.value;
    renderProducts();
  });

  document.querySelector("#clear-filters").addEventListener("click", () => {
    state.category = "Todos";
    state.search = "";
    searchInput.value = "";
    renderProducts();
    searchInput.focus();
  });

  document.addEventListener("click", (event) => {
    // Favorite Button Click
    const favoriteButton = event.target.closest("[data-favorite]");
    if (favoriteButton) {
      event.preventDefault();
      event.stopPropagation();
      toggleFavorite(favoriteButton.dataset.favorite);
      return;
    }

    const detailsButton = event.target.closest("[data-details]");
    if (detailsButton) {
      openProductDetails(detailsButton.dataset.details);
      return;
    }

    const inquiryButton = event.target.closest("[data-inquiry]");
    if (inquiryButton) {
      const product = products.find((item) => item.id === inquiryButton.dataset.inquiry);
      contactByWhatsApp(product);
      return;
    }

    if (event.target.closest("[data-whatsapp]")) {
      contactByWhatsApp();
    }
  });

  document.addEventListener("error", (event) => {
    if (!(event.target instanceof HTMLImageElement)) return;
    event.target.classList.add("image-unavailable");
    event.target.alt = "Imagen no disponible";
  }, true);

  dialog.querySelector(".dialog-close").addEventListener("click", () => dialog.close());
  dialog.addEventListener("click", (event) => {
    if (event.target === dialog) dialog.close();
  });

  const menuToggle = document.querySelector(".menu-toggle");
  const navigation = document.querySelector("#primary-navigation");
  menuToggle.addEventListener("click", () => {
    const expanded = menuToggle.getAttribute("aria-expanded") === "true";
    menuToggle.setAttribute("aria-expanded", String(!expanded));
    menuToggle.querySelector(".sr-only").textContent = expanded ? "Abrir menú" : "Cerrar menú";
    navigation.classList.toggle("is-open", !expanded);
  });
  navigation.addEventListener("click", (event) => {
    if (event.target.closest("a")) {
      navigation.classList.remove("is-open");
      menuToggle.setAttribute("aria-expanded", "false");
      menuToggle.querySelector(".sr-only").textContent = "Abrir menú";
    }
  });

  document.addEventListener("keydown", (event) => {
    if (event.key === "/" && !["INPUT", "TEXTAREA", "SELECT"].includes(document.activeElement.tagName)) {
      event.preventDefault();
      searchInput.focus();
    }
  });

  document.querySelector("#current-year").textContent = new Date().getFullYear();

  // Async loader from REST API with fallback to static catalog-data.js
  async function loadStoreData() {
    try {
      const [productsRes, settingsRes] = await Promise.allSettled([
        fetch("/api/products", { cache: "no-store" }),
        fetch("/api/settings", { cache: "no-store" })
      ]);

      if (settingsRes.status === "fulfilled" && settingsRes.value.ok) {
        const sData = await settingsRes.value.json();
        if (sData.settings) {
          settings = sData.settings;
        }
      }

      if (productsRes.status === "fulfilled" && productsRes.value.ok) {
        const pData = await productsRes.value.json();
        if (pData.products && pData.products.length > 0) {
          products = pData.products;
        }
      }
    } catch (err) {
      console.warn("[INNOVA] Error cargando desde API, utilizando datos locales:", err);
    } finally {
      renderCategories();
      renderFeatured();
      renderProducts();
      // Check customer session after store data is loaded
      checkAuthSession();
    }
  }

  loadStoreData();
})();
