function createRadarChart(scores) {
    const canvas = document.getElementById('radarChart');
    if (!canvas) {
        console.error('No se encontró el elemento canvas con id "radarChart"');
        return;
    }
    
    const ctx = canvas.getContext('2d');
    if (!ctx) {
        console.error('No se pudo obtener el contexto 2D del canvas');
        return;
    }
    
    // Destruir el gráfico anterior si existe
    if (window.radarChartInstance) {
        window.radarChartInstance.destroy();
    }
    
    // Definir las categorías que queremos mostrar en el radar
    const categoriesToShow = [
        'technical_skills_score',
        'soft_skills_score',
        'role_experience_score',
        'education_score',
        'sector_score'
    ];

    // Filtrar y formatear solo las categorías que nos interesan
    const filteredScores = {};
    categoriesToShow.forEach(category => {
        if (scores[category] !== undefined) {
            filteredScores[category] = scores[category];
        }
    });

    // Formatear las etiquetas: quitar 'score', guiones bajos y capitalizar cada palabra
    const formattedCategories = Object.keys(filteredScores).map(label => {
        // Eliminar 'score' al final del texto
        let formatted = label.replace(/score$/i, '');
        // Reemplazar guiones bajos por espacios
        formatted = formatted.replace(/_/g, ' ');
        // Capitalizar la primera letra de cada palabra
        formatted = formatted.toLowerCase()
            .split(' ')
            .map(word => word.charAt(0).toUpperCase() + word.slice(1))
            .join(' ')
            .trim();
        return formatted;
    });
    
    const values = Object.values(filteredScores).map(Number);
    
    // Configuración del gráfico
    const config = {
        type: 'radar',
        data: {
            labels: formattedCategories,
            datasets: [{
                label: 'Puntuación',
                data: values,
                backgroundColor: 'rgba(67, 97, 238, 0.15)',
                borderColor: 'rgba(67, 97, 238, 0.8)',
                borderWidth: 2,
                borderDash: [5, 5],  // Makes the line dashed: [dash length, gap length]
                pointBackgroundColor: 'rgba(67, 97, 238, 1)',
                pointBorderColor: '#fff',
                pointHoverBackgroundColor: '#fff',
                pointHoverBorderColor: 'rgba(67, 97, 238, 0.8)',
                pointRadius: 4,
                pointHoverRadius: 6
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            elements: {
                line: {
                    borderWidth: 2
                }
            },
            plugins: {
                legend: {
                    display: false
                },
                tooltip: {
                    titleFont: {
                        size: 14,
                        weight: '600'
                    },
                    bodyFont: {
                        size: 13
                    },
                    padding: 10
                }
            },
            scales: {
                r: {
                    angleLines: {
                        display: true,
                        color: 'rgba(0, 0, 0, 0.03)',  // Reduced opacity
                        lineWidth: 1
                    },
                    grid: {
                        color: 'rgba(0, 0, 0, 0.03)',  // Reduced opacity
                        circular: true,
                        borderWidth: 0.5
                    },
                    pointLabels: {
                        color: '#2b2d42',
                        font: {
                            size: 16,
                            weight: '600',
                            family: '"Segoe UI", Tahoma, Geneva, Verdana, sans-serif'
                        },
                        padding: 15
                    },
                    // Show only 100% tick
                    ticks: {
                        backdropColor: 'transparent',
                        color: 'rgba(0, 0, 0, 0.5)',
                        stepSize: 20,
                        showLabelBackdrop: false,
                        callback: function(value) {
                            if (value === 100) return '100%';
                            return '';
                        },
                        z: 1
                    },
                    // Grid lines
                    grid: {
                        color: 'rgba(0, 0, 0, 0.2)',
                        circular: true,
                        lineWidth: 1
                    },
                    // Angle lines (spokes)
                    angleLines: {
                        display: true,
                        color: 'rgba(0, 0, 0, 0.2)'
                    },
                    // Show point labels (category names)
                    pointLabels: {
                        color: '#2b2d42',
                        font: {
                            size: 14,
                            weight: '500'
                        },
                        padding: 10
                    },
                    // Chart range
                    beginAtZero: true,
                    min: 0,
                    max: 100,
                    // Remove center label
                    afterFit: function(scale) {
                        // This ensures the center label is not shown
                        scale.drawCenterLabel = function() {};
                    }
                }
            },
            plugins: {
                legend: {
                    display: false
                },
                tooltip: {
                    callbacks: {
                        label: function(context) {
                            return context.dataset.label + ': ' + context.raw.toFixed(2) + '%';
                        }
                    },
                    titleFont: {
                        size: 14,
                        weight: 'bold'
                    },
                    bodyFont: {
                        size: 13
                    },
                    padding: 10,
                    backgroundColor: 'rgba(0, 0, 0, 0.8)',
                    titleColor: '#fff',
                    bodyColor: '#fff',
                    cornerRadius: 6,
                    displayColors: false
                }
            }
        }
    };
    
    // Crear el gráfico
    window.radarChartInstance = new Chart(ctx, config);
}
