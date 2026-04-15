// ---------------- GLOBALS ----------------
let bill_id = localStorage.getItem("bill_id") || null;
let selectedProduct =null;
let searchBar = document.getElementById("search");
let productList = document.getElementById("productList"); // optional product list container
let productPreview = document.getElementById("productPreview"); // optional product preview container

function toggleMenu() {
    document.getElementById("menu").classList.toggle("show");
}

document.addEventListener("DOMContentLoaded", () => {
    window.addProduct = addProduct;
    window.editProduct = editProduct;

    // 1️⃣ Render the bill table immediately if a bill exists
    if (bill_id) loadBill();

    const gstCheckbox = document.getElementById("gst_exclusive");
    if (gstCheckbox) {
        gstCheckbox.addEventListener("change", () => {
            loadBill(); // ✅ loadBill() will read current checked state internally
        });
    } else {
    console.log("GST checkbox not found");
    }

    // 2️⃣ Download button
    const downloadBtn = document.getElementById("downloadBtn");
    if (downloadBtn) downloadBtn.addEventListener("click", downloadBill);

});

// ---------------- INIT ----------------
if (bill_id) loadBill();

// ---------------- NAVBAR SEARCH ----------------
let navSearch = document.getElementById("search"); // navbar search input
let navSuggestions = document.getElementById("navSuggestions"); // div for suggestions

if (navSearch) {
    // Trigger search page on Enter key
    navSearch.addEventListener("keydown", function(e) {
        if (e.key === "Enter") {
            e.preventDefault(); // prevent form submission if inside a form
            let q = navSearch.value.trim();
            if (q) {
                window.location.href = "/products?q=" + encodeURIComponent(q);
            }
        }
    });

    // Autocomplete suggestions while typing
    navSearch.addEventListener("input", () => {
    let q = navSearch.value.trim();
    loadProducts(q);
    if (!q) {
        navSuggestions.innerHTML = "";
        return;
    }

        fetch("/search_product?q=" + encodeURIComponent(q))
            .then(res => res.json())
            .then(data => {
                navSuggestions.innerHTML = ""; // clear old suggestions

                if (!data.length) {
                    navSuggestions.innerHTML = "<div>No products found</div>";
                    return;
                }

                data.forEach(p => {
                    let div = document.createElement("div");
                    div.textContent = p.name;
                    div.className = "nav-suggestion-item";
                    div.addEventListener("click", () => {
                        goToSearch(p.name);
                        navSuggestions.innerHTML = "";
                    });
                    navSuggestions.appendChild(div);
                });
            });
    });
}

// Navigate to search page
function goToSearch(name) {
    window.location.href = "/products?q=" + encodeURIComponent(name);
}

// ---------------- PRODUCT AUTOCOMPLETE FOR BILLING ----------------
let searchInput = document.getElementById("billingProductSearch");
let suggestions = document.getElementById("billingSuggestions");

if (searchInput) {
    searchInput.addEventListener("input", () => {
        let q = searchInput.value.trim();
        console.log("Billing search for:", q);

        if (!q) {
            suggestions.innerHTML = "";
            selectedProduct = null;
            return;
        }

        fetch("/search_product?q=" + encodeURIComponent(q))
            .then(res => res.json())
            .then(data => {
                console.log("Billing product results:", data);

                suggestions.innerHTML = ""; // clear previous suggestions

                if (!data.length) {
                    suggestions.innerHTML = "<div>No products found</div>";
                    selectedProduct = null;
                    return;
                }

                data.forEach(p => {
                    let div = document.createElement("div");
                    div.className = "suggestion-item";
                    div.textContent = `${p.name} - ₹${p.price}`;

                    div.addEventListener("click", () => {
                        selectedProduct = { id: p.id, name: p.name, price: p.price };
                        console.log("Selected product:", selectedProduct);
                        searchInput.value = p.name;
                        suggestions.innerHTML = "";
                    });

                    suggestions.appendChild(div);
                });
            });
    });
}

// ---------------- ADD ITEM ----------------
function addItem() {

    if (!bill_id) {
        alert("Create a bill first");
        return;
    }

    if (!selectedProduct || !selectedProduct.id) {
        alert("Select product first");
        return;
    }

    let qty = Number(document.getElementById("qty").value);
    let disc = Number(document.getElementById("disc").value || 0);
    let gst = Number(document.getElementById("gst").value || 0);

    if (isNaN(qty) || qty <= 0) {
        alert("Enter valid quantity");
        return;
    }

    fetch("/add_item", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
            bill_id: Number(bill_id),
            product_id: Number(selectedProduct.id),
            quantity: qty,
            discount: disc,
            gst: gst
        })
    })
    .then(res => res.json())
    .then(data => {
        if (!data || data.status === "error") {
            alert("Failed to add item");
            console.log(data);
            return;
        }

        loadBill();

        document.getElementById("qty").value = "";
        document.getElementById("disc").value = "";
        searchInput.value = "";
        selectedProduct = null;
    })
    .catch(err => {
        console.error(err);
        alert("Server error while adding item");
    });
}

function updateItem(id) {
    let qty = parseFloat(document.getElementById(`qty-${id}`).value);
    let disc = parseFloat(document.getElementById(`disc-${id}`).value);
    let gstElem = document.getElementById(`gst-${id}`);
    let gst = gstElem ? parseFloat(gstElem.value) : 0;

    if (!qty || qty <= 0) { alert("Enter valid quantity"); return; }
    if (disc < 0 || disc > 100) { alert("Discount must be 0-100"); return; }
    if (gst < 0 || gst > 100) { alert("GST must be 0-100"); return; }

    fetch(`/update_item/${id}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ quantity: qty, discount: disc, gst: gst })
    })
    .then(res => res.json())
    .then(data => {
        if (data.status === "updated") {
            loadBill(); // refresh bill after update
        } else {
            alert("Update failed!");
        }
    })
    .catch(err => {
        console.error(err);
        alert("Error updating item");
    });
}

function deleteItem(id) {
    if (!confirm("Are you sure you want to delete this item?")) return;

    fetch(`/delete_item/${id}`, {
        method: "DELETE"
    })
    .then(res => res.json())
    .then(data => {
        if (data.status === "deleted") {
            loadBill(); // refresh bill after deletion
        } else {
            alert("Failed to delete item");
        }
    })
    .catch(err => {
        console.error(err);
        alert("Error deleting item");
    });
}

// ---------------- CREATE BILL ----------------
function createBill() {
    let customer = document.getElementById("customer").value.trim();
    if (!customer) { alert("Enter customer name"); return; }

    fetch("/create_bill", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ customer })
    })
    .then(res => res.json())
    .then(data => {
        bill_id = data.bill_id;
        localStorage.setItem("bill_id", bill_id);
        loadBill(); // render table immediately
    });
}

// ---------------- LOAD BILL ----------------
function loadBill() {
    bill_id = bill_id || localStorage.getItem("bill_id");
    if (!bill_id) return;

    const gstCheckbox = document.getElementById("gst_inclusive");
    const gstInclusive = gstCheckbox ? gstCheckbox.checked : false;

    fetch("/get_bill/" + bill_id)
    .then(res => res.json())
    .then(data => {
        let html = `<table border="1" cellpadding="8">
        <tr>
            <th>Date</th>
            <th>Item</th>
            <th>Quantity</th>
            <th>Rate</th>
            <th>Discount %</th>`;
        if (!gstInclusive) html += `<th>GST%</th>`;
        html += `<th>Amount</th>
                 <th>Action</th>
                 <th>Action</th>
        </tr>`;

        let subtotal = 0, totalGST = 0;

    data.items.forEach(i => {
        let qty = parseFloat(i.quantity);
        let unitPrice = parseFloat(i.unit_price);
        let disc = parseFloat(i.discount);
        let gst = parseFloat(i.gst);

        let gross = unitPrice * qty * (1 - disc / 100); 

        let base = gross;
        let gstAmount = 0;
        let displayAmount = 0;  

        if (gstInclusive) {
            base = gross / (1 + gst / 100);
            gstAmount = gross - base;
            subtotal += base;
            totalGST += gstAmount;
            displayAmount = gross; 
        } else {
            gstAmount = gross * gst / 100;
            subtotal += gross;      
            totalGST += gstAmount;  
            displayAmount = gross + gstAmount; 
    }

         html += `<tr>
            <td>${i.date_added.split(" ")[0]}</td>
            <td>${i.name}</td>
            <td><input type="number" min="0.1" step="0.1" id="qty-${i.id}" value="${qty}" style="width:60px"></td>
            <td>₹${unitPrice.toFixed(2)}</td>
            <td><input type="number" min="0" max="100" step="0.1" id="disc-${i.id}" value="${disc}" style="width:60px"></td>`;
    
        if (!gstInclusive) {
            html += `<td><input type="number" min="0" max="100" step="0.1" id="gst-${i.id}" value="${gst}" style="width:60px"></td>`;
        }

        html += `<td>₹${displayAmount.toFixed(2)}</td>
             <td><button type="button" onclick="updateItem(${i.id})">Update</button></td>
             <td><button type="button" onclick="deleteItem(${i.id})">Delete</button></td>
        </tr>`;
    });

        let total = subtotal + totalGST;

        html += `</table> 
        <div style="margin-top:20px; padding:15px; background:#f5f5f5; border-radius:8px;">`;

        if (gstInclusive) {
            html += `
            <h3>Base Amount: ₹${subtotal.toFixed(2)}</h3>
            <h3>GST (included): ₹${totalGST.toFixed(2)}</h3>
            <h2>Total: ₹${total.toFixed(2)}</h2>
            `;
        } else {
            html += `
            <h3>Subtotal: ₹${subtotal.toFixed(2)}</h3>
            <h3>Total GST: ₹${totalGST.toFixed(2)}</h3>
            <h2>Total: ₹${total.toFixed(2)}</h2>
            `;
}

html += `
    <h3>Paid: ₹${data.paid.toFixed(2)}</h3>
    <h2 style="color:${total - data.paid > 0 ? 'red' : 'green'};">
        Balance: ₹${(total - data.paid).toFixed(2)}
    </h2>
</div>`;

        const billDiv = document.getElementById("bill");
    if (billDiv) {
        billDiv.innerHTML = html;
    }
    });
}


// ---------------- ADD PAYMENT ----------------
function addPayment() {
    const amount = parseFloat(document.getElementById("payAmount").value);
    if (!amount || amount <= 0) { alert("Enter valid amount"); return; }

    fetch("/add_payment", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ bill_id, amount })
    }).then(() => {
        loadBill();
        document.getElementById("payAmount").value = "";
    });
}

// Function to download PDF
function downloadBill() {
    if (!bill_id) { alert("No bill selected"); return; }

    const gstExclusiveCheckbox = document.getElementById("gst_exclusive");
    const gstExclusive = gstExclusiveCheckbox && gstExclusiveCheckbox.checked ? 1 : 0;
    window.open(`/download_bill/${bill_id}?gst_exclusive=${gstExclusive}`, "_blank");
}

// ---------------- DOWNLOAD PDF ----------------


document.addEventListener("DOMContentLoaded", () => {

    const productList = document.getElementById("productList");

    console.log("productList:", productList);

// ---------------- ADD PRODUCT ----------------
window.addProduct = function() {
    let name = document.getElementById("pname").value.trim();
    let price = parseFloat(document.getElementById("pprice").value);

    if (!name || isNaN(price)) {
        alert("Enter valid product details");
        return;
    }

    fetch("/add_product", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({name, price})
    })
    .then(res => res.json())
    .then(data => {
        if (!data.success) {
            alert("Failed to add product");
            return;
        }

        const product = data.product;
        const div = document.createElement("div");
        div.className = "product-row";
        div.id = `product-${data.id}`;
        div.innerHTML = `
            <span>${product.name} - ₹${product.price}</span>
            <button onclick="editProduct(${product.id}, '${encodeURIComponent(product.name)}', ${product.price})">Edit</button>
            <button onclick="deleteProduct(${product.id})">Delete</button>
        `;
        productList.prepend(div);

        document.getElementById("pname").value = "";
        document.getElementById("pprice").value = "";
    });
};
    // ---------------- EDIT PRODUCT ----------------
    window.editProduct = function(id, oldName, oldPrice) {
        let name = decodeURIComponent(oldName);

        let newName = prompt("Enter new name:", name);
        if (newName === null) return;

        let newPriceStr = prompt("Enter new price:", oldPrice);
        if (newPriceStr === null) return;

        let newPrice = parseFloat(newPriceStr);
        if (isNaN(newPrice)) {
            alert("Invalid price");
            return;
        }

        fetch("/update_product/" + id, {
            method: "PUT",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify({name: newName, price: newPrice})
        })
        .then(res => res.json())
        .then(data => {
            if (!data.success) return alert("Update failed");

            const rows = document.querySelectorAll(".product-row");

            rows.forEach(row => {
                const btn = row.querySelector("button");

                if (btn && btn.getAttribute("onclick").includes(`editProduct(${id}`)) {

                    row.querySelector("span").textContent = `${newName} - ₹${newPrice}`;

                    btn.setAttribute(
                        "onclick",
                        `editProduct(${id}, '${encodeURIComponent(newName)}', ${newPrice})`
                    );
                }
            });
        });
    };

});

// ---------------- LOAD PRODUCTS (UPDATED) ----------------
window.loadProducts = function(query=""){
        let url = query
            ? "/search_product?q=" + encodeURIComponent(query)
            : "/get_products";

        fetch(url)
        .then(res => res.json())
        .then(data => {

            // PRODUCTS PAGE
            if (productList) {
                let html = "";
                data.forEach(p => {
                    html += `
                        <div class="product-row" id="product-${p.id}">
                            <span>${p.name} - ₹${p.price}</span>
                            <button onclick="editProduct(${p.id}, '${encodeURIComponent(p.name)}', ${p.price})">Edit</button>
                            <button onclick="deleteProduct(${p.id})">Delete</button>
                        </div>
                    `;
                });
                productList.innerHTML = html;
            }

            // HOME PAGE
            if (productPreview) {
                let preview = query ? data : data.slice(0, 30);
                let html = "";
                preview.forEach(p => {
                    html += `
                        <div class="product-card">
                            <h4>${p.name}</h4>
                            <p>₹${p.price}</p>
                        </div>
                    `;
                });
                productPreview.innerHTML = html;
            }
        });
    }

    
// ----------DELETE----------
window.deleteProduct = function(id) {
    if (!confirm("Are you sure you want to delete this product?")) return;

    fetch("/delete_product/" + id, { method: "DELETE" })
        .then(res => res.json())
        .then(data => {
            if (data.success) {
                loadProducts(); // 🔥 BEST SOLUTION: refresh list
            } else {
                alert("Failed to delete product");
            }
        });
};

    // ---------------- INITIAL LOAD ----------------
    const params = new URLSearchParams(window.location.search);
    const q = params.get("q") || "";
    if (q && searchBar) {
    searchBar.value = q;
    }
    loadProducts(q);
;

// ---------------- CUSTOMERS ----------------

// Get search input and result container
let customerSearch = document.getElementById("searchCustomer");
let customerResults = document.getElementById("customerResults");

// SEARCH CUSTOMERS
if (customerSearch) {
    customerSearch.oninput = () => {
        fetch("/search_bill?name=" + encodeURIComponent(customerSearch.value))
        .then(r => r.json())
        .then(d => {
            customerResults.innerHTML = d.map(c =>
                `<div>
                    <span onclick="openCustomer(${c.id})" style="cursor:pointer;">${c.customer_name}</span>
                    <button onclick="deleteCustomer(${c.id})">Delete</button>
                </div>`
            ).join("");
        });
    };
}

// OPEN BILL FOR CUSTOMER
function openCustomer(id) {
    localStorage.setItem("bill_id", id);
    window.location.href = "/billing";
}

// DELETE CUSTOMER AND THEIR BILLS
function deleteCustomer(id) {
    if (!confirm("Delete this customer and all their bills?")) return;

    fetch("/delete_customer/" + id, { method: "DELETE" })
    .then(() => {
        // Refresh search results and full customer list if needed
        if (customerSearch.value.length > 0) {
            customerSearch.oninput();
        }
        loadCustomers();
    });
}

// LOAD ALL CUSTOMERS ON PAGE
function loadCustomers() {
    fetch("/get_customers")
    .then(res => res.json())
    .then(data => {
        let html = "";

        data.forEach(c => {
            html += `
            <div>
                <span onclick="openCustomer(${c.id})" style="cursor:pointer;">${c.customer_name}</span>
                <button onclick="deleteCustomer(${c.id})">Delete</button>
            </div>`;
        });

        document.getElementById("customerList").innerHTML = html;
    });
}

// INITIAL LOAD
loadCustomers()
;

function loadDashboard() {
    fetch("/api/month_comparison")
    .then(r => r.json())
    .then(cmp => {
        document.getElementById("monthCompare").innerHTML =
        `
        <h3>This Month: ₹${cmp.this_month}</h3>
        <h3>Last Month: ₹${cmp.last_month}</h3>
        <h3 style="color:${cmp.growth >= 0 ? 'green' : 'red'};">
            Growth: ${cmp.growth}%
        </h3>
        `;
    });

    // ONLY RUN IF ELEMENTS EXIST
    const todayEl = document.getElementById("today");
    const monthEl = document.getElementById("month");
    const yearEl = document.getElementById("year");
    const pendingEl = document.getElementById("pending");
    const chartEl = document.getElementById("productChart");
    const customersEl = document.getElementById("customers");

    // If dashboard page not loaded → stop everything
    if (!todayEl && !monthEl && !pendingEl && !chartEl) return;

    // -------- SALES OVERVIEW --------
    fetch("/api/sales_overview")
        .then(r => r.json())
        .then(sales => {
            if (todayEl) todayEl.innerText = sales.today;
            if (monthEl) monthEl.innerText = sales.month;
            if (yearEl) yearEl.innerText = sales.year;
        });

    // -------- CREDIT --------
    fetch("/api/credit_total")
        .then(r => r.json())
        .then(credit => {
            if (pendingEl) pendingEl.innerText = credit.pending;
        });

    // -------- PRODUCTS --------
    fetch("/api/top_products")
    .then(r => r.json())
    .then(products => {

        // 🔥 destroy old chart if exists (IMPORTANT)
        if (chartEl) 
            { new Chart(document.getElementById("productChart"), 
                {   type: "bar", 
                    data: { 
                        labels: products.map(p => p.name), 
                        datasets: [{ 
                            label: "Quantity Sold", 
                            data: products.map(p => p.qty),
                    backgroundColor: [
                        "#a6d5a8",
                        "#7eb0d8",
                        "#ebc285",
                        "#a46aaf",
                        "#c7756f",
                        "#607D8B",
                        "#795548",
                        "#63a5ad",
                        "#809a61",
                        "#a4976e"
                    ],
                    borderRadius: 6
                }]
            }    
        });
    }
    });

    // -------- CUSTOMERS --------
    fetch("/api/customer_insights")
        .then(r => r.json())
        .then(customers => {

            if (!customersEl) return;

            customersEl.innerHTML =
                "<h3>Total Customers: " + customers.total_customers + "</h3>";

            customers.top_customers.forEach(c => {
                customersEl.innerHTML +=
                    `<p>${c.customer_name} - ₹${c.total}</p>`;
            });
        });
}
document.addEventListener("DOMContentLoaded", () => {
    if (window.location.pathname === "/dashboard") {
        loadDashboard();
    }
});

