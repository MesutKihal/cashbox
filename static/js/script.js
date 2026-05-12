document.addEventListener("DOMContentLoaded", (event) => {
  
  const products = [
      {"title": "mordjane",
      "price": 280},
      {"title": "label",
      "price": 170},
      {"title": "cab",
      "price": 140},
      {"title": "edam",
      "price": 800},
      {"title": "kachir",
      "price": 70}
  ]
/*
                  <div class="productCard">
                    Prod01
                    <img src="{{ url_for('static', filename='assets/img/prod.png') }}" alt="">
                    <p>1580 In Stock</p>
                    <h3>130.00</h3>
                </div>

*/
  const bill = document.querySelector("#billBody tbody template")
  function createTableRow(title, price, quantity) {
      let data = {"quantity": quantity, "price": price, "subtotal": price*quantity}
      // Create Main Row
      let tr = document.createElement('tr')
      tr.setAttribute('id', "tr")
      tr.setAttribute('x-data', JSON.stringify(data))
      tr.setAttribute('id', "tr")
      tr.setAttribute('style', "cursor: pointer;")
      // Create columns
      let removeCol = document.createElement('td')
      removeCol.setAttribute("class", "btn-small bg-danger")
      removeCol.innerText = "X"
      let titleCol = document.createElement('td')
      titleCol.innerText = title
      let priceCol = document.createElement('td')
      priceCol.innerText = price
      priceCol.setAttribute("x-text", "price.toFixed(2)")
      let quantityCol = document.createElement('td')
      quantityCol.setAttribute("x-text", "quantity")
      quantityCol.innerText = quantity
      let totalCol = document.createElement('td')
      totalCol.innerText = price
      totalCol.setAttribute("x-text", "subtotal.toFixed(2)")
      let addCol = document.createElement('td')
      addCol.innerText = "+"
      addCol.setAttribute("class", "btn-small bg-success")
      addCol.setAttribute("@click", "quantity++; total += price; subtotal = quantity * price")
      let subCol = document.createElement('td')
      subCol.innerText = "-"
      subCol.setAttribute("class", "btn-small bg-danger")
      subCol.setAttribute("@click", "if(quantity > 1) {quantity--; total -= price; subtotal = quantity * price}")
      tr.append(removeCol, titleCol, priceCol, quantityCol, totalCol, addCol, subCol)
      bill.appendChild(tr)
  }

  // products.forEach(element => {
  //    createTableRow(element.title, element.price, 1)
  // });
  searchQuery: '',
filtered: null, // This will hold our search results

    // Add this function to your x-data:
    search() {
        if (!this.searchQuery) {
            this.filtered = null;
            return;
        }
        const fuse = new Fuse(this.list, { keys: ['title'] });
        this.filtered = fuse.search(this.searchQuery).map(r => r.item);
    }
})
