// Function to filter items
function filterItems() {
    // Get selected category
    const selectedCategory = categoryFilter.value;
  
    // Get items based on category (dummy example)
    const items = [
      { name: 'Item 1', category: 'clothing', price: 20 },
      { name: 'Item 2', category: 'accessories', price: 30 },
      { name: 'Item 3', category: 'electronics', price: 50 },
      // Add more items here
    ];
  
    // Filter items based on selected category
    const filteredItems = selectedCategory === 'all' ? items : items.filter(item => item.category === selectedCategory);
  
    // Display filtered items (dummy example)
    console.log(filteredItems);
  }
  
  // Function to update price value display
  function updatePriceValue() {
    priceValue.textContent = priceFilter.value;
  }
  