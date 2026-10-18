(() => {
  // Global Admin Application State
  const state = {
    user: null,
    currentSection: "dashboard",
    products: [],
    categories: [],
    promotions: [],
    settings: {},
    editingProduct: null,
    editingImages: [],
    editingSpecs: [],
    pendingDeleteAction: null
  };

  // DOM Elements
  const authView = document.querySelector("#auth-view");
  const appView = document.querySelector("#app-view");
  const loginForm = document.querySelector("#login-form");
  const loginError = document.querySelector("#login-error");
  const loginSubmit = document.querySelector("#login-submit");
  const togglePasswordBtn = document.querySelector("#toggle-password");
  const logoutBtn = document.querySelector("#logout-btn");
  const sidebar = document.querySelector("#app-sidebar");
  const sidebarToggle = document.querySelector("#sidebar-toggle");
  const sidebarClose = document.querySelector("#sidebar-close");
  const pageTitle = document.querySelector("#page-title");
  const toastContainer = document.querySelector("#toast-container");

  // Formatters
  function formatPrice(amount) {
    const symbol = state.settings.currency_symbol || "$";
    const formatted = new Intl.NumberFormat("es-CO", { maximumFractionDigits: 0 }).format(amount || 0);
    return `${symbol} ${formatted}`;
  }

  function formatDate(dateStr) {
    if (!dateStr) return "-";
    try {
      const d = new Date(dateStr.replace(" ", "T"));
      return d.toLocaleDateString("es-CO", {
        year: "numeric",
        month: "short",
        day: "numeric",
        hour: "2-digit",
        minute: "2-digit"
      });
    } catch {
      return dateStr;
    }
  }

  // Toast Notification System
  function showToast(message, type = "success") {
    const toast = document.createElement("div");
    toast.className = `toast-item toast-${type}`;
    const icon = type === "success" ? "✓" : type === "error" ? "✕" : "ℹ";
    toast.innerHTML = `<span style="font-weight:700;">${icon}</span> <span>${message}</span>`;
    toastContainer.appendChild(toast);
    setTimeout(() => {
      toast.style.opacity = "0";
      toast.style.transform = "translateY(10px)";
      toast.style.transition = "all 0.2s ease";
      setTimeout(() => toast.remove(), 250);
    }, 3800);
  }

  // Modal Dialog Helpers
  function openModal(modalId) {
    const modal = document.querySelector(`#${modalId}`);
    if (modal) {
      if (typeof modal.showModal === "function") {
        modal.showModal();
      } else {
        modal.setAttribute("open", "");
      }
    }
  }

  function closeModal(modalId) {
    const modal = document.querySelector(`#${modalId}`);
    if (modal) {
      if (typeof modal.close === "function") {
        modal.close();
      } else {
        modal.removeAttribute("open");
      }
    }
  }

  document.querySelectorAll("[data-close-modal]").forEach((btn) => {
    btn.addEventListener("click", () => {
      closeModal(btn.dataset.closeModal);
    });
  });

  // ========================================================
  // AUTHENTICATION LOGIC
  // ========================================================
  async function checkAuth() {
    try {
      const res = await fetch("/api/auth/me", { cache: "no-store" });
      if (res.ok) {
        const data = await res.json();
        setAuthenticated(data.user);
      } else {
        setUnauthenticated();
      }
    } catch (err) {
      setUnauthenticated();
    }
  }

  function setAuthenticated(user) {
    state.user = user;
    authView.hidden = true;
    appView.hidden = false;

    document.querySelector("#user-display-name").textContent = user.username;
    document.querySelector("#user-display-role").textContent = user.role || "Administrador";
    document.querySelector("#user-avatar-initial").textContent = (user.username[0] || "A").toUpperCase();

    // Load initial settings and navigate to initial route
    loadSettings().then(() => {
      handleRoute();
    });
  }

  function setUnauthenticated() {
    state.user = null;
    authView.hidden = false;
    appView.hidden = true;
  }

  loginForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    loginError.hidden = true;
    const identifier = document.querySelector("#login-identifier").value.trim();
    const password = document.querySelector("#login-password").value;

    if (!identifier || !password) {
      loginError.textContent = "Por favor completa todos los campos.";
      loginError.hidden = false;
      return;
    }

    loginSubmit.disabled = true;
    loginSubmit.querySelector(".btn-text").hidden = true;
    loginSubmit.querySelector(".btn-spinner").hidden = false;

    try {
      const res = await fetch("/api/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ identifier, password })
      });

      const data = await res.json();
      if (res.ok && data.success) {
        showToast(`Bienvenido al panel, ${data.user.username}`);
        setAuthenticated(data.user);
      } else {
        loginError.textContent = data.error || "Credenciales incorrectas.";
        loginError.hidden = false;
      }
    } catch (err) {
      loginError.textContent = "Error de conexión con el servidor.";
      loginError.hidden = false;
    } finally {
      loginSubmit.disabled = false;
      loginSubmit.querySelector(".btn-text").hidden = false;
      loginSubmit.querySelector(".btn-spinner").hidden = true;
    }
  });

  logoutBtn.addEventListener("click", async () => {
    try {
      await fetch("/api/auth/logout", { method: "POST" });
    } finally {
      showToast("Sesión cerrada correctamente.");
      setUnauthenticated();
    }
  });

  togglePasswordBtn.addEventListener("click", () => {
    const input = document.querySelector("#login-password");
    if (input.type === "password") {
      input.type = "text";
      togglePasswordBtn.textContent = "🙈";
    } else {
      input.type = "password";
      togglePasswordBtn.textContent = "👁️";
    }
  });

  // ========================================================
  // NAVIGATION & ROUTING
  // ========================================================
  function handleRoute() {
    const hash = window.location.hash.replace("#", "") || "dashboard";
    navigateTo(hash);
  }

  window.addEventListener("hashchange", handleRoute);

  function navigateTo(sectionName) {
    state.currentSection = sectionName;
    document.querySelectorAll(".nav-item").forEach((item) => {
      item.classList.toggle("active", item.dataset.nav === sectionName);
    });

    document.querySelectorAll(".content-section").forEach((sec) => {
      sec.classList.remove("active");
      sec.hidden = true;
    });

    const targetSection = document.querySelector(`#section-${sectionName}`);
    if (targetSection) {
      targetSection.classList.add("active");
      targetSection.hidden = false;
    }

    const titles = {
      dashboard: "Dashboard Resumen",
      products: "Gestión de Productos",
      inventory: "Control de Inventario",
      promotions: "Promociones y Descuentos",
      categories: "Categorías de Productos",
      notifications: "Comunicaciones y Notificaciones",
      settings: "Configuración de la Tienda"
    };
    pageTitle.textContent = titles[sectionName] || "Administración";

    // Close mobile sidebar if open
    sidebar.classList.remove("is-open");

    // Load section data
    if (sectionName === "dashboard") loadDashboard();
    else if (sectionName === "products") loadProducts();
    else if (sectionName === "inventory") loadInventory();
    else if (sectionName === "promotions") loadPromotions();
    else if (sectionName === "categories") loadCategories();
    else if (sectionName === "settings") loadSettings();
  }

  sidebarToggle.addEventListener("click", () => sidebar.classList.add("is-open"));
  sidebarClose.addEventListener("click", () => sidebar.classList.remove("is-open"));

  // ========================================================
  // DASHBOARD MODULE
  // ========================================================
  async function loadDashboard() {
    try {
      const res = await fetch("/api/dashboard", { cache: "no-store" });
      if (!res.ok) return;
      const data = await res.json();
      const m = data.metrics;

      document.querySelector("#metric-total").textContent = m.total_products;
      document.querySelector("#metric-active").textContent = m.active_products;
      document.querySelector("#metric-out").textContent = m.out_of_stock;
      document.querySelector("#metric-low").textContent = m.low_stock;
      document.querySelector("#metric-low-sub").textContent = `Umbral: ≤ ${m.low_stock_threshold} unid.`;
      document.querySelector("#metric-promos").textContent = m.active_promotions;
      const custMetric = document.querySelector("#metric-customers");
      if (custMetric) custMetric.textContent = m.total_customers || 0;

      // Latest products table
      const pTbody = document.querySelector("#dashboard-products-table tbody");
      if (data.latest_products && data.latest_products.length > 0) {
        pTbody.innerHTML = data.latest_products.map((p) => `
          <tr>
            <td><strong>${p.name}</strong></td>
            <td>${p.category_name || "-"}</td>
            <td>${formatPrice(p.price)}</td>
            <td>
              <span class="badge ${p.stock <= 0 ? "badge-danger" : p.stock <= m.low_stock_threshold ? "badge-warning" : "badge-success"}">
                ${p.stock} unid.
              </span>
            </td>
            <td>
              <span class="badge ${p.status === "active" ? "badge-success" : p.status === "draft" ? "badge-warning" : "badge-muted"}">
                ${p.status === "active" ? "Activo" : p.status === "draft" ? "Borrador" : "Inactivo"}
              </span>
            </td>
          </tr>
        `).join("");
      } else {
        pTbody.innerHTML = `<tr><td colspan="5" class="empty-state">No hay productos registrados aún.</td></tr>`;
      }

      // Recent stock movements table
      const mTbody = document.querySelector("#dashboard-movements-table tbody");
      if (data.recent_movements && data.recent_movements.length > 0) {
        mTbody.innerHTML = data.recent_movements.map((mv) => `
          <tr>
            <td><small>${formatDate(mv.created_at)}</small></td>
            <td>${mv.product_name || mv.product_id}</td>
            <td>
              <strong style="color: ${mv.delta >= 0 ? "var(--success)" : "var(--danger)"};">
                ${mv.delta >= 0 ? "+" + mv.delta : mv.delta}
              </strong>
            </td>
            <td>${mv.new_stock} unid.</td>
            <td><small>${mv.reason || "-"}</small></td>
          </tr>
        `).join("");
      } else {
        mTbody.innerHTML = `<tr><td colspan="5" class="empty-state">No hay movimientos registrados aún.</td></tr>`;
      }
    } catch (err) {
      console.error("Error loading dashboard:", err);
    }
  }

  document.querySelector("#btn-quick-new-product").addEventListener("click", () => openProductModal());
  document.querySelector("#btn-quick-inventory").addEventListener("click", () => {
    window.location.hash = "#inventory";
  });
  document.querySelector("#btn-quick-promo").addEventListener("click", () => openPromotionModal());

  // ========================================================
  // PRODUCTS MODULE
  // ========================================================
  async function loadProducts() {
    try {
      await loadCategoriesList();
      const res = await fetch("/api/products?all=1", { cache: "no-store" });
      if (!res.ok) return;
      const data = await res.json();
      state.products = data.products || [];
      renderProductsTable();
    } catch (err) {
      showToast("Error cargando productos", "error");
    }
  }

  function renderProductsTable() {
    const search = document.querySelector("#product-filter-search").value.trim().toLowerCase();
    const category = document.querySelector("#product-filter-category").value;
    const status = document.querySelector("#product-filter-status").value;
    const sort = document.querySelector("#product-filter-sort").value;

    let filtered = state.products.filter((p) => {
      const matchSearch = !search ||
        (p.name && p.name.toLowerCase().includes(search)) ||
        (p.sku && p.sku.toLowerCase().includes(search)) ||
        (p.short_description && p.short_description.toLowerCase().includes(search));
      const matchCat = category === "Todos" || (p.category_name === category);
      const matchStatus = !status || (p.status === status);
      return matchSearch && matchCat && matchStatus;
    });

    // Sorting
    if (sort === "price-asc") filtered.sort((a, b) => a.price - b.price);
    else if (sort === "price-desc") filtered.sort((a, b) => b.price - a.price);
    else if (sort === "stock-asc") filtered.sort((a, b) => a.stock - b.stock);
    else if (sort === "name-asc") filtered.sort((a, b) => a.name.localeCompare(b.name));
    else filtered.sort((a, b) => Number(b.featured) - Number(a.featured));

    const tbody = document.querySelector("#products-table tbody");
    const emptyState = document.querySelector("#products-empty-state");

    if (filtered.length === 0) {
      tbody.innerHTML = "";
      emptyState.hidden = false;
      return;
    }

    emptyState.hidden = true;
    tbody.innerHTML = filtered.map((p) => {
      const hasDiscount = Boolean(p.has_discount);
      const displayPrice = hasDiscount ? p.effective_price : p.price;
      const thumb = p.primary_image || (p.images && p.images[0] ? p.images[0].image_url : "/assets/innova-mark.png");

      return `
        <tr>
          <td><img src="${thumb}" alt="" class="table-thumb"></td>
          <td>
            <strong>${p.name}</strong><br>
            <small style="color:var(--text-muted);">${p.sku || p.id}</small>
          </td>
          <td>${p.category_name || "-"}</td>
          <td>${formatPrice(p.price)}</td>
          <td>
            ${hasDiscount ? `
              <strong style="color:var(--text-primary);">${formatPrice(displayPrice)}</strong>
              <span class="badge badge-warning" style="margin-left:4px;">-${p.discount_percent}%</span>
            ` : `<span style="color:var(--text-secondary);">${formatPrice(p.price)}</span>`}
          </td>
          <td>
            <span class="badge ${p.stock <= 0 ? "badge-danger" : p.stock_status === "low_stock" ? "badge-warning" : "badge-success"}">
              ${p.stock <= 0 ? "Agotado (0)" : p.stock + " unid."}
            </span>
          </td>
          <td>
            <button type="button" class="badge ${p.status === "active" ? "badge-success" : p.status === "draft" ? "badge-warning" : "badge-muted"}"
                    data-toggle-status="${p.id}" data-current-status="${p.status}" title="Clic para alternar estado">
              ${p.status === "active" ? "Activo" : p.status === "draft" ? "Borrador" : "Inactivo"}
            </button>
          </td>
          <td>
            <button type="button" class="btn-icon" data-toggle-featured="${p.id}" data-current-featured="${p.featured ? "1" : "0"}" title="Destacado">
              ${p.featured ? "⭐" : "☆"}
            </button>
          </td>
          <td style="text-align: right; white-space: nowrap;">
            <button type="button" class="btn btn-outline btn-sm" data-duplicate-product="${p.id}" title="Duplicar como borrador">Duplicar</button>
            <button type="button" class="btn btn-outline btn-sm" data-edit-product="${p.id}">Editar</button>
            <button type="button" class="btn btn-danger btn-sm" data-delete-product="${p.id}">✕</button>
          </td>
        </tr>
      `;
    }).join("");
  }

  // Filter Listeners
  document.querySelector("#product-filter-search").addEventListener("input", renderProductsTable);
  document.querySelector("#product-filter-category").addEventListener("change", renderProductsTable);
  document.querySelector("#product-filter-status").addEventListener("change", renderProductsTable);
  document.querySelector("#product-filter-sort").addEventListener("change", renderProductsTable);

  document.querySelector("#products-table").addEventListener("click", async (e) => {
    const dupBtn = e.target.closest("[data-duplicate-product]");
    if (dupBtn) {
      const prodId = dupBtn.dataset.duplicateProduct;
      if (!confirm("¿Deseas duplicar este producto como un nuevo borrador?")) return;
      dupBtn.disabled = true;
      try {
        const res = await fetch(`/api/products/${prodId}/duplicate`, { method: "POST" });
        const data = await res.json();
        if (res.ok && data.success) {
          showToast("Producto duplicado exitosamente como borrador.");
          loadProducts();
        } else {
          showToast(data.error || "No se pudo duplicar el producto", "error");
        }
      } catch (err) {
        showToast("Error de conexión al duplicar producto", "error");
      }
      return;
    }

    const editBtn = e.target.closest("[data-edit-product]");
    if (editBtn) return openProductModal(editBtn.dataset.editProduct);

    const deleteBtn = e.target.closest("[data-delete-product]");
    if (deleteBtn) return confirmDelete("product", deleteBtn.dataset.deleteProduct);

    const statusBtn = e.target.closest("[data-toggle-status]");
    if (statusBtn) {
      const nextStatus = statusBtn.dataset.currentStatus === "active" ? "inactive" : "active";
      return updateProductStatus(statusBtn.dataset.toggleStatus, nextStatus);
    }

    const featuredBtn = e.target.closest("[data-toggle-featured]");
    if (featuredBtn) {
      const nextFeatured = featuredBtn.dataset.currentFeatured === "1" ? false : true;
      return updateProductFeatured(featuredBtn.dataset.toggleFeatured, nextFeatured);
    }
  });

  async function updateProductStatus(prodId, newStatus) {
    try {
      const res = await fetch(`/api/products/${prodId}/status`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ status: newStatus })
      });
      if (res.ok) {
        showToast("Estado de producto actualizado");
        loadProducts();
      }
    } catch {
      showToast("Error al cambiar estado", "error");
    }
  }

  async function updateProductFeatured(prodId, newFeatured) {
    try {
      const res = await fetch(`/api/products/${prodId}/featured`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ featured: newFeatured })
      });
      if (res.ok) {
        showToast("Producto actualizado");
        loadProducts();
      }
    } catch {
      showToast("Error al cambiar estado destacado", "error");
    }
  }

  // Product Create / Edit Modal
  document.querySelector("#btn-open-create-product").addEventListener("click", () => openProductModal());

  async function openProductModal(prodId = null) {
    await loadCategoriesList();
    const form = document.querySelector("#form-product");
    form.reset();
    state.editingImages = [];
    state.editingSpecs = [];
    document.querySelector("#prod-discount-indicator").textContent = "";

    const catSelect = document.querySelector("#prod-category");
    catSelect.innerHTML = state.categories.map((c) => `<option value="${c.id}">${c.name}</option>`).join("");

    if (prodId) {
      document.querySelector("#modal-product-title").textContent = "Editar Producto";
      try {
        const res = await fetch(`/api/products/${prodId}`, { cache: "no-store" });
        if (!res.ok) throw new Error();
        const data = await res.json();
        const p = data.product;
        state.editingProduct = p;

        document.querySelector("#prod-id").value = p.id;
        document.querySelector("#prod-name").value = p.name;
        document.querySelector("#prod-category").value = p.category_id || "";
        document.querySelector("#prod-sku").value = p.sku || "";
        document.querySelector("#prod-price").value = p.price;
        document.querySelector("#prod-promo-price").value = p.promo_price ?? "";
        document.querySelector("#prod-stock").value = p.stock;
        document.querySelector("#prod-status").value = p.status;
        document.querySelector("#prod-featured").checked = Boolean(p.featured);
        document.querySelector("#prod-short-desc").value = p.short_description || "";
        document.querySelector("#prod-full-desc").value = p.full_description || "";

        state.editingImages = (p.images || []).map((img) => ({
          image_url: img.image_url,
          is_primary: Boolean(img.is_primary)
        }));

        state.editingSpecs = Array.isArray(p.specs) ? [...p.specs] : [];
        updatePromoPriceIndicator();
      } catch {
        showToast("Error al cargar producto", "error");
        return;
      }
    } else {
      document.querySelector("#modal-product-title").textContent = "Nuevo Producto";
      document.querySelector("#prod-id").value = "";
      state.editingProduct = null;
    }

    renderGalleryPreviews();
    renderSpecsList();
    openModal("modal-product");
  }

  // Promotional price live calculation & validation in modal
  function updatePromoPriceIndicator() {
    const normalPrice = parseFloat(document.querySelector("#prod-price").value) || 0;
    const promoPriceInput = document.querySelector("#prod-promo-price").value;
    const indicator = document.querySelector("#prod-discount-indicator");

    if (!promoPriceInput) {
      indicator.textContent = "";
      return;
    }

    const promoPrice = parseFloat(promoPriceInput);
    if (isNaN(promoPrice) || promoPrice < 0) {
      indicator.style.color = "var(--danger)";
      indicator.textContent = "El precio debe ser un número positivo.";
    } else if (promoPrice >= normalPrice) {
      indicator.style.color = "var(--danger)";
      indicator.textContent = "El precio promocional debe ser menor al precio normal.";
    } else {
      const pct = Math.round(((normalPrice - promoPrice) / normalPrice) * 100);
      indicator.style.color = "var(--success)";
      indicator.textContent = `Ahorro para el cliente: ${pct}% de descuento (-${formatPrice(normalPrice - promoPrice)})`;
    }
  }

  document.querySelector("#prod-price").addEventListener("input", updatePromoPriceIndicator);
  document.querySelector("#prod-promo-price").addEventListener("input", updatePromoPriceIndicator);

  // Specifications builder
  function renderSpecsList() {
    const list = document.querySelector("#specs-list");
    list.innerHTML = state.editingSpecs.map((spec, idx) => `
      <li>
        <span>${spec}</span>
        <button type="button" data-remove-spec="${idx}" aria-label="Eliminar especificación">✕</button>
      </li>
    `).join("");
  }

  document.querySelector("#btn-add-spec").addEventListener("click", () => {
    const input = document.querySelector("#spec-input");
    const val = input.value.trim();
    if (val) {
      state.editingSpecs.push(val);
      input.value = "";
      renderSpecsList();
    }
  });

  document.querySelector("#specs-list").addEventListener("click", (e) => {
    const removeBtn = e.target.closest("[data-remove-spec]");
    if (removeBtn) {
      const idx = parseInt(removeBtn.dataset.removeSpec, 10);
      state.editingSpecs.splice(idx, 1);
      renderSpecsList();
    }
  });

  // Images Gallery & Upload
  function renderGalleryPreviews() {
    const gallery = document.querySelector("#product-images-gallery");
    gallery.innerHTML = state.editingImages.map((img, idx) => `
      <div class="image-preview-card">
        <img src="${img.image_url}" alt="">
        ${img.is_primary ? '<span class="primary-indicator-badge">Principal</span>' : ""}
        <div class="image-preview-actions">
          ${!img.is_primary ? `<button type="button" class="btn-icon" data-set-primary="${idx}" title="Establecer como principal">★</button>` : "<span></span>"}
          <button type="button" class="btn-icon" data-remove-img="${idx}" title="Eliminar imagen">✕</button>
        </div>
      </div>
    `).join("");
  }

  document.querySelector("#btn-trigger-upload").addEventListener("click", () => {
    document.querySelector("#prod-file-input").click();
  });

  document.querySelector("#prod-file-input").addEventListener("change", async (e) => {
    const files = Array.from(e.target.files);
    if (!files.length) return;

    for (const file of files) {
      if (file.size > 5 * 1024 * 1024) {
        showToast(`El archivo ${file.name} supera el límite de 5MB`, "error");
        continue;
      }

      const formData = new FormData();
      formData.append("file", file);

      try {
        const res = await fetch("/api/upload", {
          method: "POST",
          body: formData
        });
        const data = await res.json();
        if (res.ok && data.url) {
          const isFirst = state.editingImages.length === 0;
          state.editingImages.push({
            image_url: data.url,
            is_primary: isFirst
          });
          renderGalleryPreviews();
          showToast(`Imagen ${file.name} subida exitosamente.`);
        } else {
          showToast(data.error || "Error al subir imagen", "error");
        }
      } catch (err) {
        showToast("Error de conexión durante la subida", "error");
      }
    }
    e.target.value = "";
  });

  document.querySelector("#btn-add-image-url").addEventListener("click", () => {
    const input = document.querySelector("#prod-image-url-input");
    const url = input.value.trim();
    if (url) {
      const isFirst = state.editingImages.length === 0;
      state.editingImages.push({
        image_url: url,
        is_primary: isFirst
      });
      input.value = "";
      renderGalleryPreviews();
    }
  });

  document.querySelector("#product-images-gallery").addEventListener("click", (e) => {
    const primaryBtn = e.target.closest("[data-set-primary]");
    if (primaryBtn) {
      const idx = parseInt(primaryBtn.dataset.setPrimary, 10);
      state.editingImages.forEach((img, i) => { img.is_primary = (i === idx); });
      renderGalleryPreviews();
      return;
    }

    const removeBtn = e.target.closest("[data-remove-img]");
    if (removeBtn) {
      const idx = parseInt(removeBtn.dataset.removeImg, 10);
      const wasPrimary = state.editingImages[idx].is_primary;
      state.editingImages.splice(idx, 1);
      if (wasPrimary && state.editingImages.length > 0) {
        state.editingImages[0].is_primary = true;
      }
      renderGalleryPreviews();
      return;
    }
  });

  // Save Product Submission
  document.querySelector("#form-product").addEventListener("submit", async (e) => {
    e.preventDefault();
    const prodId = document.querySelector("#prod-id").value;
    const name = document.querySelector("#prod-name").value.trim();
    const category_id = parseInt(document.querySelector("#prod-category").value, 10);
    const sku = document.querySelector("#prod-sku").value.trim();
    const price = parseFloat(document.querySelector("#prod-price").value);
    const promoVal = document.querySelector("#prod-promo-price").value.trim();
    const promo_price = promoVal !== "" ? parseFloat(promoVal) : null;
    const stock = parseInt(document.querySelector("#prod-stock").value, 10);
    const status = document.querySelector("#prod-status").value;
    const featured = document.querySelector("#prod-featured").checked;
    const short_description = document.querySelector("#prod-short-desc").value.trim();
    const full_description = document.querySelector("#prod-full-desc").value.trim();

    if (promo_price !== null && promo_price >= price) {
      showToast("El precio promocional debe ser menor al precio normal", "error");
      return;
    }

    const payload = {
      name,
      category_id,
      sku,
      price,
      promo_price,
      stock,
      status,
      featured,
      short_description,
      full_description,
      specs: state.editingSpecs,
      images: state.editingImages
    };

    const isEdit = Boolean(prodId);
    const url = isEdit ? `/api/products/${prodId}` : "/api/products";
    const method = isEdit ? "PUT" : "POST";

    try {
      const res = await fetch(url, {
        method,
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });
      const data = await res.json();
      if (res.ok && data.success) {
        showToast(isEdit ? "Producto actualizado correctamente" : "Producto creado correctamente");
        closeModal("modal-product");
        loadProducts();
      } else {
        showToast(data.error || "Error al guardar producto", "error");
      }
    } catch {
      showToast("Error de conexión al guardar producto", "error");
    }
  });

  // ========================================================
  // INVENTORY MODULE
  // ========================================================
  async function loadInventory() {
    const filterBtn = document.querySelector("#inventory-filter-group .btn.active");
    const filter = filterBtn ? filterBtn.dataset.invFilter : "all";
    const search = document.querySelector("#inventory-search").value.trim();

    try {
      const res = await fetch(`/api/inventory?filter=${encodeURIComponent(filter)}&search=${encodeURIComponent(search)}`, { cache: "no-store" });
      if (!res.ok) return;
      const data = await res.json();
      renderInventoryTable(data.inventory, data.threshold);

      // Also load movements
      loadStockMovements();
    } catch {
      showToast("Error al cargar inventario", "error");
    }
  }

  function renderInventoryTable(items, threshold) {
    const tbody = document.querySelector("#inventory-table tbody");
    if (!items || items.length === 0) {
      tbody.innerHTML = `<tr><td colspan="6" class="empty-state">No se encontraron productos en inventario.</td></tr>`;
      return;
    }

    tbody.innerHTML = items.map((item) => {
      const thumb = item.image_url || "/assets/innova-mark.png";
      const isOut = item.stock <= 0;
      const isLow = !isOut && item.stock <= threshold;

      return `
        <tr>
          <td><img src="${thumb}" alt="" class="table-thumb"></td>
          <td>
            <strong>${item.name}</strong><br>
            <small style="color:var(--text-muted);">${item.sku || item.id}</small>
          </td>
          <td>${item.category_name || "-"}</td>
          <td>
            <span style="font-size:16px; font-weight:700; color: ${isOut ? "var(--danger)" : isLow ? "var(--warning)" : "var(--success)"};">
              ${item.stock} unidades
            </span>
          </td>
          <td>
            <span class="badge ${isOut ? "badge-danger" : isLow ? "badge-warning" : "badge-success"}">
              ${isOut ? "Agotado" : isLow ? `Bajo (≤ ${threshold})` : "Saludable"}
            </span>
          </td>
          <td style="text-align: right;">
            <div style="display:inline-flex; gap:6px;">
              <button type="button" class="btn btn-outline btn-sm" data-quick-delta="${item.id}" data-delta="-1" title="Restar 1 unidad" ${isOut ? "disabled" : ""}>-1</button>
              <button type="button" class="btn btn-outline btn-sm" data-quick-delta="${item.id}" data-delta="1" title="Sumar 1 unidad">+1</button>
              <button type="button" class="btn btn-outline btn-sm" data-quick-delta="${item.id}" data-delta="5" title="Sumar 5 unidades">+5</button>
              <button type="button" class="btn btn-secondary btn-sm" data-open-adjust="${item.id}" data-stock="${item.stock}" data-name="${item.name}">Ajustar...</button>
              ${!isOut ? `<button type="button" class="btn btn-danger btn-sm" data-mark-soldout="${item.id}" title="Marcar como agotado (0)">Agotar</button>` : ""}
            </div>
          </td>
        </tr>
      `;
    }).join("");
  }

  async function loadStockMovements() {
    try {
      const res = await fetch("/api/inventory/movements?limit=30", { cache: "no-store" });
      if (!res.ok) return;
      const data = await res.json();
      const tbody = document.querySelector("#inventory-movements-full-table tbody");
      if (!data.movements || data.movements.length === 0) {
        tbody.innerHTML = `<tr><td colspan="7" class="empty-state">No hay registros de movimientos aún.</td></tr>`;
        return;
      }

      tbody.innerHTML = data.movements.map((m) => `
        <tr>
          <td><small>${formatDate(m.created_at)}</small></td>
          <td>
            <strong>${m.product_name || m.product_id}</strong><br>
            <small style="color:var(--text-muted);">${m.product_sku || ""}</small>
          </td>
          <td>${m.previous_stock} unid.</td>
          <td>
            <strong style="color: ${m.delta >= 0 ? "var(--success)" : "var(--danger)"};">
              ${m.delta >= 0 ? "+" + m.delta : m.delta}
            </strong>
          </td>
          <td><strong>${m.new_stock} unid.</strong></td>
          <td>${m.reason || "-"}</td>
          <td><small>${m.user_name || "Sistema"}</small></td>
        </tr>
      `).join("");
    } catch (err) {
      console.error("Error loading stock movements:", err);
    }
  }

  // Filter group in inventory
  document.querySelectorAll("#inventory-filter-group [data-inv-filter]").forEach((btn) => {
    btn.addEventListener("click", () => {
      document.querySelectorAll("#inventory-filter-group [data-inv-filter]").forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");
      loadInventory();
    });
  });

  document.querySelector("#inventory-search").addEventListener("input", loadInventory);

  document.querySelector("#inventory-table").addEventListener("click", async (e) => {
    const quickDelta = e.target.closest("[data-quick-delta]");
    if (quickDelta) {
      const prodId = quickDelta.dataset.quickDelta;
      const delta = parseInt(quickDelta.dataset.delta, 10);
      const action = delta > 0 ? "add" : "subtract";
      return submitStockAdjustment(prodId, action, Math.abs(delta), "Ajuste rápido desde tabla de inventario");
    }

    const soldOutBtn = e.target.closest("[data-mark-soldout]");
    if (soldOutBtn) {
      const prodId = soldOutBtn.dataset.markSoldout;
      return submitStockAdjustment(prodId, "set", 0, "Producto marcado como agotado");
    }

    const adjustBtn = e.target.closest("[data-open-adjust]");
    if (adjustBtn) {
      const prodId = adjustBtn.dataset.openAdjust;
      const name = adjustBtn.dataset.name;
      const stock = parseInt(adjustBtn.dataset.stock, 10);
      openAdjustModal(prodId, name, stock);
      return;
    }
  });

  function openAdjustModal(prodId, name, currentStock) {
    document.querySelector("#adjust-product-id").value = prodId;
    document.querySelector("#adjust-product-name").textContent = name;
    document.querySelector("#adjust-current-stock").textContent = `Existencias actuales: ${currentStock} unidades`;
    document.querySelector("#adjust-quantity").value = "";
    document.querySelector("#adjust-reason").value = "";
    updateAdjustPreview();
    openModal("modal-inventory-adjust");
  }

  function updateAdjustPreview() {
    const currentStockText = document.querySelector("#adjust-current-stock").textContent;
    const match = currentStockText.match(/(\d+)/);
    const current = match ? parseInt(match[1], 10) : 0;
    const action = document.querySelector("input[name='adjust-action']:checked")?.value || "add";
    const qty = parseInt(document.querySelector("#adjust-quantity").value, 10) || 0;

    let res = current;
    if (action === "add") res = current + qty;
    else if (action === "subtract") res = Math.max(0, current - qty);
    else if (action === "set") res = qty;

    document.querySelector("#adjust-resulting-stock").textContent = `${res} unidades`;
  }

  document.querySelectorAll("input[name='adjust-action']").forEach((r) => r.addEventListener("change", updateAdjustPreview));
  document.querySelector("#adjust-quantity").addEventListener("input", updateAdjustPreview);

  document.querySelector("#form-inventory-adjust").addEventListener("submit", async (e) => {
    e.preventDefault();
    const prodId = document.querySelector("#adjust-product-id").value;
    const action = document.querySelector("input[name='adjust-action']:checked").value;
    const quantity = parseInt(document.querySelector("#adjust-quantity").value, 10);
    const reason = document.querySelector("#adjust-reason").value.trim();

    await submitStockAdjustment(prodId, action, quantity, reason);
    closeModal("modal-inventory-adjust");
  });

  async function submitStockAdjustment(productId, action, quantity, reason) {
    try {
      const res = await fetch("/api/inventory/adjust", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ product_id: productId, action, quantity, reason })
      });
      const data = await res.json();
      if (res.ok && data.success) {
        showToast("Inventario actualizado correctamente");
        loadInventory();
      } else {
        showToast(data.error || "Error al actualizar inventario", "error");
      }
    } catch {
      showToast("Error de conexión al ajustar inventario", "error");
    }
  }

  // ========================================================
  // PROMOTIONS MODULE
  // ========================================================
  async function loadPromotions() {
    try {
      const res = await fetch("/api/promotions", { cache: "no-store" });
      if (!res.ok) return;
      const data = await res.json();
      state.promotions = data.promotions || [];
      renderPromotionsTable();
    } catch {
      showToast("Error cargando promociones", "error");
    }
  }

  function renderPromotionsTable() {
    const tbody = document.querySelector("#promotions-table tbody");
    const emptyState = document.querySelector("#promotions-empty-state");

    if (state.promotions.length === 0) {
      tbody.innerHTML = "";
      emptyState.hidden = false;
      return;
    }

    emptyState.hidden = true;
    tbody.innerHTML = state.promotions.map((p) => {
      const discountText = p.discount_type === "percent" ? `${p.discount_value}%` : formatPrice(p.discount_value);
      const statusClass = p.status === "active" ? "badge-success" : p.status === "scheduled" ? "badge-info" : p.status === "expired" ? "badge-muted" : "badge-danger";
      const statusLabel = p.status === "active" ? "Vigente / Activa" : p.status === "scheduled" ? "Programada" : p.status === "expired" ? "Vencida" : "Desactivada";

      return `
        <tr>
          <td>
            <strong>${p.name}</strong><br>
            <small style="color:var(--text-muted);">${p.description || "-"}</small>
          </td>
          <td><strong style="color:var(--warning); font-size:14px;">-${discountText}</strong></td>
          <td>${p.target_name || "Todos los productos"}</td>
          <td>
            <small>${formatDate(p.starts_at)}<br>→ ${formatDate(p.ends_at)}</small>
          </td>
          <td><span class="badge ${statusClass}">${statusLabel}</span></td>
          <td>
            <input type="checkbox" ${p.is_active ? "checked" : ""} data-toggle-promo-active="${p.id}" style="cursor:pointer;">
          </td>
          <td style="text-align: right;">
            <button type="button" class="btn btn-outline btn-sm" data-edit-promo="${p.id}">Editar</button>
            <button type="button" class="btn btn-danger btn-sm" data-delete-promo="${p.id}">✕</button>
          </td>
        </tr>
      `;
    }).join("");
  }

  document.querySelector("#btn-open-create-promo").addEventListener("click", () => openPromotionModal());

  async function openPromotionModal(promoId = null) {
    await loadCategoriesList();
    if (!state.products.length) {
      const res = await fetch("/api/products?all=1");
      const d = await res.json();
      state.products = d.products || [];
    }

    const form = document.querySelector("#form-promotion");
    form.reset();

    const targetTypeSelect = document.querySelector("#promo-target-type");
    targetTypeSelect.value = "all";
    updatePromoTargetSelector();

    if (promoId) {
      document.querySelector("#modal-promo-title").textContent = "Editar Promoción";
      const p = state.promotions.find((item) => item.id === parseInt(promoId, 10));
      if (!p) return;

      document.querySelector("#promo-id").value = p.id;
      document.querySelector("#promo-name").value = p.name;
      document.querySelector("#promo-desc").value = p.description || "";
      document.querySelector("#promo-type").value = p.discount_type;
      document.querySelector("#promo-value").value = p.discount_value;
      document.querySelector("#promo-target-type").value = p.target_type;
      updatePromoTargetSelector();
      if (p.target_id) document.querySelector("#promo-target-id").value = p.target_id;

      document.querySelector("#promo-starts-at").value = (p.starts_at || "").replace(" ", "T").substring(0, 16);
      document.querySelector("#promo-ends-at").value = (p.ends_at || "").replace(" ", "T").substring(0, 16);
      document.querySelector("#promo-active").checked = Boolean(p.is_active);
    } else {
      document.querySelector("#modal-promo-title").textContent = "Nueva Promoción";
      document.querySelector("#promo-id").value = "";
      // Default dates: now until 7 days ahead
      const now = new Date();
      const nextWeek = new Date(now.getTime() + 7 * 86400000);
      document.querySelector("#promo-starts-at").value = now.toISOString().substring(0, 16);
      document.querySelector("#promo-ends-at").value = nextWeek.toISOString().substring(0, 16);
    }

    openModal("modal-promotion");
  }

  function updatePromoTargetSelector() {
    const targetType = document.querySelector("#promo-target-type").value;
    const wrap = document.querySelector("#promo-target-select-wrap");
    const select = document.querySelector("#promo-target-id");
    const label = document.querySelector("#promo-target-id-label");

    if (targetType === "all") {
      wrap.hidden = true;
      select.required = false;
    } else if (targetType === "category") {
      wrap.hidden = false;
      select.required = true;
      label.textContent = "Seleccionar Categoría";
      select.innerHTML = state.categories.map((c) => `<option value="${c.id}">${c.name}</option>`).join("");
    } else if (targetType === "product") {
      wrap.hidden = false;
      select.required = true;
      label.textContent = "Seleccionar Producto";
      select.innerHTML = state.products.map((p) => `<option value="${p.id}">${p.name} (${p.sku || p.id})</option>`).join("");
    }
  }

  document.querySelector("#promo-target-type").addEventListener("change", updatePromoTargetSelector);

  document.querySelector("#form-promotion").addEventListener("submit", async (e) => {
    e.preventDefault();
    const promoId = document.querySelector("#promo-id").value;
    const name = document.querySelector("#promo-name").value.trim();
    const description = document.querySelector("#promo-desc").value.trim();
    const discount_type = document.querySelector("#promo-type").value;
    const discount_value = parseFloat(document.querySelector("#promo-value").value);
    const target_type = document.querySelector("#promo-target-type").value;
    const target_id = target_type !== "all" ? document.querySelector("#promo-target-id").value : null;
    const starts_at = document.querySelector("#promo-starts-at").value;
    const ends_at = document.querySelector("#promo-ends-at").value;
    const is_active = document.querySelector("#promo-active").checked;

    if (ends_at <= starts_at) {
      showToast("La fecha de finalización debe ser posterior a la de inicio", "error");
      return;
    }

    const payload = {
      name,
      description,
      discount_type,
      discount_value,
      target_type,
      target_id,
      starts_at,
      ends_at,
      is_active
    };

    const isEdit = Boolean(promoId);
    const url = isEdit ? `/api/promotions/${promoId}` : "/api/promotions";
    const method = isEdit ? "PUT" : "POST";

    try {
      const res = await fetch(url, {
        method,
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });
      const data = await res.json();
      if (res.ok && data.success) {
        showToast(isEdit ? "Promoción actualizada" : "Promoción creada exitosamente");
        closeModal("modal-promotion");
        loadPromotions();
      } else {
        showToast(data.error || "Error al guardar promoción", "error");
      }
    } catch {
      showToast("Error de conexión al guardar promoción", "error");
    }
  });

  document.querySelector("#promotions-table").addEventListener("click", async (e) => {
    const editBtn = e.target.closest("[data-edit-promo]");
    if (editBtn) return openPromotionModal(editBtn.dataset.editPromo);

    const deleteBtn = e.target.closest("[data-delete-promo]");
    if (deleteBtn) return confirmDelete("promotion", deleteBtn.dataset.deletePromo);

    const toggleCheckbox = e.target.closest("[data-toggle-promo-active]");
    if (toggleCheckbox) {
      const promoId = toggleCheckbox.dataset.togglePromoActive;
      const isActive = toggleCheckbox.checked;
      try {
        const res = await fetch(`/api/promotions/${promoId}/status`, {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ is_active: isActive })
        });
        if (res.ok) {
          showToast("Estado de promoción actualizado");
          loadPromotions();
        }
      } catch {
        showToast("Error al alternar estado", "error");
      }
    }
  });

  // ========================================================
  // CATEGORIES MODULE
  // ========================================================
  async function loadCategoriesList() {
    try {
      const res = await fetch("/api/categories", { cache: "no-store" });
      if (!res.ok) return;
      const data = await res.json();
      state.categories = data.categories || [];

      // Update public filter selector in products toolbar
      const catFilter = document.querySelector("#product-filter-category");
      if (catFilter) {
        const currentVal = catFilter.value;
        catFilter.innerHTML = '<option value="Todos">Todas las categorías</option>' +
          state.categories.map((c) => `<option value="${c.name}">${c.name}</option>`).join("");
        catFilter.value = currentVal;
      }
    } catch (err) {
      console.error("Error loading categories:", err);
    }
  }

  async function loadCategories() {
    await loadCategoriesList();
    const tbody = document.querySelector("#categories-table tbody");
    if (state.categories.length === 0) {
      tbody.innerHTML = `<tr><td colspan="5" class="empty-state">No hay categorías registradas.</td></tr>`;
      return;
    }

    tbody.innerHTML = state.categories.map((c) => `
      <tr>
        <td><strong>${c.name}</strong></td>
        <td><code>${c.slug}</code></td>
        <td>${c.description || "-"}</td>
        <td>
          <span class="badge badge-info">${c.product_count || 0} productos</span>
        </td>
        <td style="text-align: right;">
          <button type="button" class="btn btn-outline btn-sm" data-edit-category="${c.id}" data-name="${c.name}" data-desc="${c.description || ""}">Editar</button>
          <button type="button" class="btn btn-danger btn-sm" data-delete-category="${c.id}" data-count="${c.product_count || 0}">✕</button>
        </td>
      </tr>
    `).join("");
  }

  document.querySelector("#btn-open-create-category").addEventListener("click", () => {
    document.querySelector("#modal-category-title").textContent = "Nueva Categoría";
    document.querySelector("#category-id").value = "";
    document.querySelector("#category-name").value = "";
    document.querySelector("#category-desc").value = "";
    openModal("modal-category");
  });

  document.querySelector("#categories-table").addEventListener("click", (e) => {
    const editBtn = e.target.closest("[data-edit-category]");
    if (editBtn) {
      document.querySelector("#modal-category-title").textContent = "Editar Categoría";
      document.querySelector("#category-id").value = editBtn.dataset.editCategory;
      document.querySelector("#category-name").value = editBtn.dataset.name;
      document.querySelector("#category-desc").value = editBtn.dataset.desc;
      openModal("modal-category");
      return;
    }

    const deleteBtn = e.target.closest("[data-delete-category]");
    if (deleteBtn) {
      const count = parseInt(deleteBtn.dataset.count, 10);
      if (count > 0) {
        showToast(`No se puede eliminar la categoría porque tiene ${count} productos asociados. Reasigna los productos primero.`, "error");
        return;
      }
      return confirmDelete("category", deleteBtn.dataset.deleteCategory);
    }
  });

  document.querySelector("#form-category").addEventListener("submit", async (e) => {
    e.preventDefault();
    const catId = document.querySelector("#category-id").value;
    const name = document.querySelector("#category-name").value.trim();
    const description = document.querySelector("#category-desc").value.trim();

    const isEdit = Boolean(catId);
    const url = isEdit ? `/api/categories/${catId}` : "/api/categories";
    const method = isEdit ? "PUT" : "POST";

    try {
      const res = await fetch(url, {
        method,
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name, description })
      });
      const data = await res.json();
      if (res.ok && data.success) {
        showToast(isEdit ? "Categoría actualizada" : "Categoría creada");
        closeModal("modal-category");
        loadCategories();
      } else {
        showToast(data.error || "Error al guardar categoría", "error");
      }
    } catch {
      showToast("Error de conexión", "error");
    }
  });

  // ========================================================
  // SETTINGS MODULE
  // ========================================================
  async function loadSettings() {
    try {
      const res = await fetch("/api/settings", { cache: "no-store" });
      if (!res.ok) return;
      const data = await res.json();
      state.settings = data.settings || {};

      document.querySelector("#setting-store-name").value = state.settings.store_name || "INNOVA";
      document.querySelector("#setting-store-tagline").value = state.settings.store_tagline || "";
      document.querySelector("#setting-whatsapp-url").value = state.settings.whatsapp_url || "";
      document.querySelector("#setting-whatsapp-phone").value = state.settings.whatsapp_phone || "";
      document.querySelector("#setting-contact-email").value = state.settings.contact_email || "";
      document.querySelector("#setting-currency-code").value = state.settings.currency_code || "COP";
      document.querySelector("#setting-currency-symbol").value = state.settings.currency_symbol || "$";
      document.querySelector("#setting-low-stock-threshold").value = state.settings.low_stock_threshold || "5";
      document.querySelector("#setting-announcement").value = state.settings.announcement || "";
    } catch (err) {
      console.error("Error loading settings:", err);
    }
  }

  document.querySelector("#settings-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const payload = {
      store_name: document.querySelector("#setting-store-name").value.trim(),
      store_tagline: document.querySelector("#setting-store-tagline").value.trim(),
      whatsapp_url: document.querySelector("#setting-whatsapp-url").value.trim(),
      whatsapp_phone: document.querySelector("#setting-whatsapp-phone").value.trim(),
      contact_email: document.querySelector("#setting-contact-email").value.trim(),
      currency_code: document.querySelector("#setting-currency-code").value.trim(),
      currency_symbol: document.querySelector("#setting-currency-symbol").value.trim(),
      low_stock_threshold: document.querySelector("#setting-low-stock-threshold").value.trim(),
      announcement: document.querySelector("#setting-announcement").value.trim()
    };

    try {
      const res = await fetch("/api/settings", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });
      const data = await res.json();
      if (res.ok && data.success) {
        showToast("Configuración guardada exitosamente");
        state.settings = payload;
      } else {
        showToast(data.error || "Error al guardar configuración", "error");
      }
    } catch {
      showToast("Error de conexión al guardar configuración", "error");
    }
  });

  // ========================================================
  // CONFIRMATION DIALOG (DELETE)
  // ========================================================
  function confirmDelete(entityType, entityId) {
    state.pendingDeleteAction = { entityType, entityId };
    const titles = {
      product: "Eliminar Producto",
      promotion: "Eliminar Promoción",
      category: "Eliminar Categoría"
    };
    const messages = {
      product: `¿Estás seguro de que deseas eliminar este producto? Se eliminarán también sus referencias e imágenes asociadas.`,
      promotion: `¿Estás seguro de que deseas eliminar esta promoción? Dejará de aplicarse inmediatamente.`,
      category: `¿Estás seguro de que deseas eliminar esta categoría?`
    };

    document.querySelector("#confirm-title").textContent = titles[entityType] || "Confirmar";
    document.querySelector("#confirm-message").textContent = messages[entityType] || "¿Deseas continuar?";
    openModal("modal-confirm");
  }

  document.querySelector("#btn-confirm-delete").addEventListener("click", async () => {
    if (!state.pendingDeleteAction) return;
    const { entityType, entityId } = state.pendingDeleteAction;
    closeModal("modal-confirm");

    const endpointMap = {
      product: `/api/products/${entityId}`,
      promotion: `/api/promotions/${entityId}`,
      category: `/api/categories/${entityId}`
    };

    const url = endpointMap[entityType];
    if (!url) return;

    try {
      const res = await fetch(url, { method: "DELETE" });
      const data = await res.json();
      if (res.ok && data.success) {
        showToast("Elemento eliminado exitosamente");
        if (entityType === "product") loadProducts();
        else if (entityType === "promotion") loadPromotions();
        else if (entityType === "category") loadCategories();
      } else {
        showToast(data.error || "Error al eliminar elemento", "error");
      }
    } catch {
      showToast("Error de conexión", "error");
    } finally {
      state.pendingDeleteAction = null;
    }
  });

  // ========================================================
  // NOTIFICATIONS MODULE (ADMIN BROADCAST)
  // ========================================================
  const notifForm = document.querySelector("#form-send-notification");
  if (notifForm) {
    notifForm.addEventListener("submit", async (e) => {
      e.preventDefault();
      const alertBox = document.querySelector("#notif-broadcast-alert");
      alertBox.hidden = true;
      const btn = document.querySelector("#btn-broadcast-notif");
      
      const target = document.querySelector("#notif-target").value;
      const type = document.querySelector("#notif-type").value;
      const title = document.querySelector("#notif-title").value.trim();
      const message = document.querySelector("#notif-message").value.trim();
      const link_url = document.querySelector("#notif-link").value.trim();

      if (!title || !message) {
        alertBox.className = "alert alert-error";
        alertBox.textContent = "Por favor ingresa un título y un mensaje para la notificación.";
        alertBox.hidden = false;
        return;
      }

      btn.disabled = true;
      btn.querySelector(".btn-text").hidden = true;
      btn.querySelector(".btn-spinner").hidden = false;

      try {
        const res = await fetch("/api/admin/notifications", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ target, type, title, message, link_url })
        });
        const data = await res.json();
        if (res.ok && data.success) {
          alertBox.className = "alert alert-success";
          alertBox.textContent = `Notificación enviada con éxito. Se entregó a ${data.recipients_count} cliente(s) según sus preferencias.`;
          alertBox.hidden = false;
          showToast(`Campaña emitida a ${data.recipients_count} clientes.`);
          notifForm.reset();
        } else {
          alertBox.className = "alert alert-error";
          alertBox.textContent = data.error || "No se pudo emitir la notificación.";
          alertBox.hidden = false;
        }
      } catch (err) {
        alertBox.className = "alert alert-error";
        alertBox.textContent = "Error de conexión al emitir notificación.";
        alertBox.hidden = false;
      } finally {
        btn.disabled = false;
        btn.querySelector(".btn-text").hidden = false;
        btn.querySelector(".btn-spinner").hidden = true;
      }
    });
  }

  // Kickstart Application
  checkAuth();
})();

