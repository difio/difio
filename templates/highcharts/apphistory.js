$(function () {
    var chart;
    $(document).ready(function() {
        chart = new Highcharts.Chart({
            chart: {
                renderTo: 'chart',
                type: 'scatter',
                inverted: true,
                zoomType : 'y',
            },
            title: {
                text: null,
            },

            xAxis: {
                categories: [{{ categories|safe }}],
                gridLineWidth: 0,
                labels : { enabled: false },
            },
            yAxis: {
                gridLineWidth: 0,
                labels : { enabled: false },
                plotLines: [{
                    value: 0,
                    width: 1,
                    color: '#808080'
                }]
            },
            tooltip: {
                formatter: function() {
                        return '<b>'+ this.series.name +'</b>'+
                        this.point.name;
                }
            },
            legend: {
                layout: 'vertical',
                align: 'left',
                verticalAlign: 'top',
                x: 0,
                y: 0,
                borderWidth: 1,
            },
            plotOptions: {
                line: { marker: { enabled: false } },
            },

            series: [
{{ versions|safe }}
{{ current_state|safe }}
            ]
        });
    });
});
