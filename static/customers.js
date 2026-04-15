// LOAD ALL CUSTOMERS
function loadCustomers() {
    fetch("/get_customers")
    .then(res => res.json())
    .then(data => {
        let html = "";

        data.forEach(c => {
            html += `
            <div>
                <span onclick="openCustomer(${c.id})">${c.customer_name}</span>
                <button onclick="deleteCustomer(${c.id})">Delete</button>
            </div>`;
        });

        document.getElementById("customerList").innerHTML = html;
    });
}

function openCustomer(id) {
    localStorage.setItem("bill_id", id);
    window.location.href = "/billing";
}

// DELETE CUSTOMER
function deleteCustomer(id) {
    if (!confirm("Delete this customer?")) return;

    fetch("/delete_customer/" + id, { method: "DELETE" })
    .then(() => loadCustomers());
}

// SEARCH CUSTOMERS
let customerSearch = document.getElementById("searchCustomer");
let customerResults = document.getElementById("customerResults");

if (customerSearch) {
    customerSearch.oninput = () => {
        fetch("/search_bill?name=" + customerSearch.value)
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

loadCustomers();