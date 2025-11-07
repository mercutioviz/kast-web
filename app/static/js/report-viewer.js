// Report Viewer - Expand/Collapse functionality for tree view

document.addEventListener('DOMContentLoaded', function() {
    // Initialize tree view expand/collapse functionality
    initializeTreeView();
});

function initializeTreeView() {
    // Find all tree toggle elements
    const toggles = document.querySelectorAll('.tree-toggle');
    
    toggles.forEach(function(toggle) {
        // Add click event listener
        toggle.addEventListener('click', function(e) {
            e.preventDefault();
            e.stopPropagation();
            
            // Find the next sibling that is .tree-children
            let treeChildren = toggle.nextElementSibling;
            
            // Skip over .tree-key if it's between toggle and children
            while (treeChildren && !treeChildren.classList.contains('tree-children')) {
                treeChildren = treeChildren.nextElementSibling;
            }
            
            if (treeChildren && treeChildren.classList.contains('tree-children')) {
                // Toggle visibility
                if (treeChildren.style.display === 'none') {
                    treeChildren.style.display = '';
                    toggle.textContent = '[-]';
                } else {
                    treeChildren.style.display = 'none';
                    toggle.textContent = '[+]';
                }
            }
        });
        
        // Add pointer cursor to indicate clickability
        toggle.style.cursor = 'pointer';
        toggle.style.userSelect = 'none';
        
        // Set initial state based on toggle text
        let treeChildren = toggle.nextElementSibling;
        while (treeChildren && !treeChildren.classList.contains('tree-children')) {
            treeChildren = treeChildren.nextElementSibling;
        }
        
        if (treeChildren && toggle.textContent.trim() === '[+]') {
            treeChildren.style.display = 'none';
        }
    });
}
