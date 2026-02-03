"""
AgentWatch Dashboard Server

Serves the monitoring dashboard with real-time updates.
"""

import os
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
import uvicorn

app = FastAPI(title="AgentWatch Dashboard")

# Get the dashboard directory
DASHBOARD_DIR = Path(__file__).parent

# Serve static files
if (DASHBOARD_DIR / "static").exists():
    app.mount("/static", StaticFiles(directory=DASHBOARD_DIR / "static"), name="static")


@app.get("/", response_class=HTMLResponse)
async def dashboard():
    """Serve the main dashboard."""
    html_path = DASHBOARD_DIR / "index.html"
    if html_path.exists():
        return html_path.read_text()
    return get_embedded_dashboard()


def get_embedded_dashboard():
    """Return embedded dashboard HTML."""
    return """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AgentWatch - AI Agent Observability</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
    <style>
        body { font-family: 'Inter', sans-serif; }
        .gradient-bg { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); }
        .card { background: white; border-radius: 12px; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1); }
        .metric-card { transition: transform 0.2s; }
        .metric-card:hover { transform: translateY(-2px); }
        .status-dot { width: 8px; height: 8px; border-radius: 50%; }
        .status-running { background: #fbbf24; animation: pulse 2s infinite; }
        .status-success { background: #10b981; }
        .status-error { background: #ef4444; }
        @keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.5; } }
        .activity-feed { max-height: 400px; overflow-y: auto; }
        .chart-container { position: relative; height: 300px; }
    </style>
</head>
<body class="bg-gray-50 min-h-screen">
    <!-- Header -->
    <header class="gradient-bg text-white shadow-lg">
        <div class="container mx-auto px-6 py-4">
            <div class="flex items-center justify-between">
                <div class="flex items-center space-x-3">
                    <svg class="w-8 h-8" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z"/>
                    </svg>
                    <h1 class="text-2xl font-bold">AgentWatch</h1>
                </div>
                <div class="flex items-center space-x-4">
                    <span id="lastUpdate" class="text-sm opacity-75">Last update: --</span>
                    <span class="px-3 py-1 bg-white/20 rounded-full text-sm">Live</span>
                </div>
            </div>
        </div>
    </header>

    <!-- Main Content -->
    <main class="container mx-auto px-6 py-8">
        <!-- Metrics Row -->
        <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
            <!-- Total Traces -->
            <div class="card p-6 metric-card">
                <div class="flex items-center justify-between">
                    <div>
                        <p class="text-gray-500 text-sm font-medium">Total Traces</p>
                        <p id="totalTraces" class="text-3xl font-bold text-gray-900 mt-1">--</p>
                    </div>
                    <div class="p-3 bg-blue-100 rounded-lg">
                        <svg class="w-6 h-6 text-blue-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10V3L4 14h7v7l9-11h-7z"/>
                        </svg>
                    </div>
                </div>
                <p class="text-sm text-gray-500 mt-2">Last 7 days</p>
            </div>

            <!-- Success Rate -->
            <div class="card p-6 metric-card">
                <div class="flex items-center justify-between">
                    <div>
                        <p class="text-gray-500 text-sm font-medium">Success Rate</p>
                        <p id="successRate" class="text-3xl font-bold text-green-600 mt-1">--</p>
                    </div>
                    <div class="p-3 bg-green-100 rounded-lg">
                        <svg class="w-6 h-6 text-green-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"/>
                        </svg>
                    </div>
                </div>
                <p id="errorCount" class="text-sm text-red-500 mt-2">-- errors</p>
            </div>

            <!-- Avg Duration -->
            <div class="card p-6 metric-card">
                <div class="flex items-center justify-between">
                    <div>
                        <p class="text-gray-500 text-sm font-medium">Avg Duration</p>
                        <p id="avgDuration" class="text-3xl font-bold text-gray-900 mt-1">--</p>
                    </div>
                    <div class="p-3 bg-purple-100 rounded-lg">
                        <svg class="w-6 h-6 text-purple-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"/>
                        </svg>
                    </div>
                </div>
                <p class="text-sm text-gray-500 mt-2">Response time</p>
            </div>

            <!-- Total Cost -->
            <div class="card p-6 metric-card">
                <div class="flex items-center justify-between">
                    <div>
                        <p class="text-gray-500 text-sm font-medium">Total Cost</p>
                        <p id="totalCost" class="text-3xl font-bold text-gray-900 mt-1">$--</p>
                    </div>
                    <div class="p-3 bg-amber-100 rounded-lg">
                        <svg class="w-6 h-6 text-amber-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/>
                        </svg>
                    </div>
                </div>
                <p id="tokenCount" class="text-sm text-gray-500 mt-2">-- tokens</p>
            </div>
        </div>

        <!-- Charts Row -->
        <div class="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-8">
            <!-- Traces Over Time -->
            <div class="card p-6">
                <h3 class="text-lg font-semibold text-gray-900 mb-4">Traces Over Time</h3>
                <div class="chart-container">
                    <canvas id="tracesChart"></canvas>
                </div>
            </div>

            <!-- Cost Over Time -->
            <div class="card p-6">
                <h3 class="text-lg font-semibold text-gray-900 mb-4">Cost Over Time</h3>
                <div class="chart-container">
                    <canvas id="costChart"></canvas>
                </div>
            </div>
        </div>

        <!-- Bottom Row -->
        <div class="grid grid-cols-1 lg:grid-cols-3 gap-6">
            <!-- Agent Performance -->
            <div class="card p-6 lg:col-span-2">
                <h3 class="text-lg font-semibold text-gray-900 mb-4">Agent Performance</h3>
                <div class="overflow-x-auto">
                    <table class="w-full">
                        <thead>
                            <tr class="text-left text-gray-500 text-sm border-b">
                                <th class="pb-3 font-medium">Agent</th>
                                <th class="pb-3 font-medium">Traces</th>
                                <th class="pb-3 font-medium">Success Rate</th>
                                <th class="pb-3 font-medium">Avg Duration</th>
                            </tr>
                        </thead>
                        <tbody id="agentTable">
                            <tr>
                                <td colspan="4" class="py-4 text-center text-gray-500">Loading...</td>
                            </tr>
                        </tbody>
                    </table>
                </div>
            </div>

            <!-- Recent Activity -->
            <div class="card p-6">
                <h3 class="text-lg font-semibold text-gray-900 mb-4">Recent Activity</h3>
                <div id="activityFeed" class="activity-feed space-y-3">
                    <div class="text-center text-gray-500 py-4">Loading...</div>
                </div>
            </div>
        </div>

        <!-- Alerts Section -->
        <div class="mt-8">
            <div class="card p-6">
                <h3 class="text-lg font-semibold text-gray-900 mb-4">Active Alerts</h3>
                <div id="alertsContainer" class="space-y-3">
                    <div class="text-center text-gray-500 py-4">No active alerts</div>
                </div>
            </div>
        </div>
    </main>

    <script>
        const API_BASE = 'http://localhost:8765';
        let tracesChart, costChart;

        // Initialize charts
        function initCharts() {
            const chartOptions = {
                responsive: true,
                maintainAspectRatio: false,
                plugins: { legend: { display: false } },
                scales: {
                    x: { grid: { display: false } },
                    y: { beginAtZero: true, grid: { color: '#f3f4f6' } }
                }
            };

            tracesChart = new Chart(document.getElementById('tracesChart'), {
                type: 'line',
                data: { labels: [], datasets: [{
                    label: 'Traces',
                    data: [],
                    borderColor: '#6366f1',
                    backgroundColor: 'rgba(99, 102, 241, 0.1)',
                    fill: true,
                    tension: 0.4
                }]},
                options: chartOptions
            });

            costChart = new Chart(document.getElementById('costChart'), {
                type: 'line',
                data: { labels: [], datasets: [{
                    label: 'Cost ($)',
                    data: [],
                    borderColor: '#f59e0b',
                    backgroundColor: 'rgba(245, 158, 11, 0.1)',
                    fill: true,
                    tension: 0.4
                }]},
                options: chartOptions
            });
        }

        // Fetch and update summary
        async function updateSummary() {
            try {
                const res = await fetch(`${API_BASE}/api/analytics/summary`);
                const data = await res.json();
                
                document.getElementById('totalTraces').textContent = data.total_traces.toLocaleString();
                document.getElementById('successRate').textContent = data.success_rate + '%';
                document.getElementById('errorCount').textContent = data.error_count + ' errors';
                document.getElementById('avgDuration').textContent = (data.avg_duration_ms / 1000).toFixed(2) + 's';
                document.getElementById('totalCost').textContent = '$' + data.total_cost.toFixed(2);
                document.getElementById('tokenCount').textContent = (data.total_input_tokens + data.total_output_tokens).toLocaleString() + ' tokens';
            } catch (e) {
                console.error('Failed to fetch summary:', e);
            }
        }

        // Fetch and update time series
        async function updateTimeSeries() {
            try {
                const [tracesRes, costRes] = await Promise.all([
                    fetch(`${API_BASE}/api/analytics/timeseries?metric=traces`),
                    fetch(`${API_BASE}/api/analytics/timeseries?metric=cost`)
                ]);
                
                const tracesData = await tracesRes.json();
                const costData = await costRes.json();

                // Update traces chart
                tracesChart.data.labels = tracesData.map(d => new Date(d.timestamp).toLocaleTimeString());
                tracesChart.data.datasets[0].data = tracesData.map(d => d.value);
                tracesChart.update();

                // Update cost chart
                costChart.data.labels = costData.map(d => new Date(d.timestamp).toLocaleTimeString());
                costChart.data.datasets[0].data = costData.map(d => d.value);
                costChart.update();
            } catch (e) {
                console.error('Failed to fetch time series:', e);
            }
        }

        // Fetch and update agent table
        async function updateAgentTable() {
            try {
                const res = await fetch(`${API_BASE}/api/analytics/agents`);
                const agents = await res.json();
                
                const tbody = document.getElementById('agentTable');
                if (agents.length === 0) {
                    tbody.innerHTML = '<tr><td colspan="4" class="py-4 text-center text-gray-500">No agents registered</td></tr>';
                    return;
                }
                
                tbody.innerHTML = agents.map(agent => `
                    <tr class="border-b last:border-0">
                        <td class="py-3">
                            <span class="font-medium text-gray-900">${agent.agent_name}</span>
                        </td>
                        <td class="py-3 text-gray-600">${agent.trace_count}</td>
                        <td class="py-3">
                            <span class="px-2 py-1 text-sm rounded-full ${agent.success_rate >= 95 ? 'bg-green-100 text-green-800' : agent.success_rate >= 80 ? 'bg-yellow-100 text-yellow-800' : 'bg-red-100 text-red-800'}">
                                ${agent.success_rate}%
                            </span>
                        </td>
                        <td class="py-3 text-gray-600">${(agent.avg_duration_ms / 1000).toFixed(2)}s</td>
                    </tr>
                `).join('');
            } catch (e) {
                console.error('Failed to fetch agents:', e);
            }
        }

        // Fetch and update activity feed
        async function updateActivityFeed() {
            try {
                const res = await fetch(`${API_BASE}/api/traces?limit=10`);
                const traces = await res.json();
                
                const feed = document.getElementById('activityFeed');
                if (traces.length === 0) {
                    feed.innerHTML = '<div class="text-center text-gray-500 py-4">No recent activity</div>';
                    return;
                }
                
                feed.innerHTML = traces.map(trace => `
                    <div class="flex items-center space-x-3 p-2 hover:bg-gray-50 rounded-lg">
                        <div class="status-dot status-${trace.status}"></div>
                        <div class="flex-1 min-w-0">
                            <p class="text-sm font-medium text-gray-900 truncate">${trace.task_type || 'Task'}</p>
                            <p class="text-xs text-gray-500">${new Date(trace.started_at).toLocaleTimeString()}</p>
                        </div>
                        <span class="text-xs text-gray-400">${trace.duration_ms ? (trace.duration_ms / 1000).toFixed(1) + 's' : '...'}</span>
                    </div>
                `).join('');
            } catch (e) {
                console.error('Failed to fetch activity:', e);
            }
        }

        // Fetch and update alerts
        async function updateAlerts() {
            try {
                const res = await fetch(`${API_BASE}/api/alerts?status=open&limit=5`);
                const alerts = await res.json();
                
                const container = document.getElementById('alertsContainer');
                if (alerts.length === 0) {
                    container.innerHTML = '<div class="text-center text-gray-500 py-4">No active alerts ✓</div>';
                    return;
                }
                
                container.innerHTML = alerts.map(alert => `
                    <div class="flex items-center justify-between p-4 rounded-lg ${alert.severity === 'critical' ? 'bg-red-50 border border-red-200' : alert.severity === 'error' ? 'bg-orange-50 border border-orange-200' : 'bg-yellow-50 border border-yellow-200'}">
                        <div class="flex items-center space-x-3">
                            <svg class="w-5 h-5 ${alert.severity === 'critical' ? 'text-red-500' : 'text-yellow-500'}" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"/>
                            </svg>
                            <div>
                                <p class="font-medium text-gray-900">${alert.title}</p>
                                <p class="text-sm text-gray-600">${alert.description || ''}</p>
                            </div>
                        </div>
                        <span class="text-xs text-gray-500">${new Date(alert.timestamp).toLocaleTimeString()}</span>
                    </div>
                `).join('');
            } catch (e) {
                console.error('Failed to fetch alerts:', e);
            }
        }

        // Update timestamp
        function updateTimestamp() {
            document.getElementById('lastUpdate').textContent = 'Last update: ' + new Date().toLocaleTimeString();
        }

        // Refresh all data
        async function refreshAll() {
            await Promise.all([
                updateSummary(),
                updateTimeSeries(),
                updateAgentTable(),
                updateActivityFeed(),
                updateAlerts()
            ]);
            updateTimestamp();
        }

        // Initialize
        document.addEventListener('DOMContentLoaded', () => {
            initCharts();
            refreshAll();
            
            // Refresh every 10 seconds
            setInterval(refreshAll, 10000);
        });
    </script>
</body>
</html>
"""


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8766)
