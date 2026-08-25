function renderSpendingChart() {
    document.querySelectorAll('.chart-bar').forEach(function (bar) {
        bar.style.height = bar.dataset.pct + '%';
    });
}

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', renderSpendingChart);
} else {
    renderSpendingChart();
}
