document.addEventListener('DOMContentLoaded', () => {
    const tabs = document.querySelectorAll('.tab');
    const contents = document.querySelectorAll('.content');
    const indicator = document.querySelector('.indicator');
  
    // Update indicator based on active tab position
    function updateIndicator(activeTab) {
      const left = activeTab.offsetLeft;
      const width = activeTab.offsetWidth;
      indicator.style.left = left + 'px';
      indicator.style.width = width + 'px';
    }
  
    // Initialize indicator position for the active tab
    updateIndicator(document.querySelector('.tab.active'));
  
    tabs.forEach(tab => {
      tab.addEventListener('click', () => {
        // Remove active class from all tabs and contents
        tabs.forEach(t => t.classList.remove('active'));
        contents.forEach(c => c.classList.remove('active'));
  
        // Add active class to clicked tab and its corresponding content
        tab.classList.add('active');
        const tabId = tab.getAttribute('data-tab');
        document.getElementById(tabId).classList.add('active');
  
        // Update indicator position
        updateIndicator(tab);
      });
    });
  });
  