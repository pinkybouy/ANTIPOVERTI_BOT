document.addEventListener('DOMContentLoaded', () => {
    const btnToggle = document.getElementById('btnToggle');
    const statusDot = document.getElementById('statusDot');
    const statusText = document.getElementById('statusText');
    const statusIndicator = document.getElementById('statusIndicator');

    // UI Elements
    const statMessages = document.getElementById('statMessages');
    const statRate = document.getElementById('statRate');
    const statPing = document.getElementById('statPing');
    const statDisk = document.getElementById('statDisk');
    const statTotalSaved = document.getElementById('statTotalSaved');
    const calculatingIndicator = document.getElementById('calculatingIndicator');
    const statBufferBar = document.getElementById('statBufferBar');
    const statBufferText = document.getElementById('statBufferText');

    const priceBTCUSDT = document.getElementById('priceBTCUSDT');
    const priceBTCUSDC = document.getElementById('priceBTCUSDC');
    const marketTimer = document.getElementById('marketTimer');

    // New TF Panel Elements
    const tfPicker = document.getElementById('tfPicker');
    const tfLabel = document.getElementById('tfLabel');
    const bigPricePanel = document.getElementById('bigPricePanel');
    const priceChangeBadge = document.getElementById('priceChangeBadge');

    let isRunning = false;
    let pollInterval;
    let clockInterval;

    // Start Market Timer (UTC)
    const updateMarketTimer = () => {
        const now = new Date();
        const hours = String(now.getUTCHours()).padStart(2, '0');
        const mins = String(now.getUTCMinutes()).padStart(2, '0');
        const secs = String(now.getUTCSeconds()).padStart(2, '0');
        marketTimer.textContent = `${hours}:${mins}:${secs}`;
    };
    clockInterval = setInterval(updateMarketTimer, 1000);
    updateMarketTimer();

    const updateStatusUI = (status) => {
        isRunning = status === 'Running';

        if (isRunning) {
            btnToggle.textContent = 'ZATRZYMAJ NA PRZERWĘ';
            btnToggle.classList.remove('bg-blue-600', 'hover:bg-blue-500', 'shadow-blue-500/30');
            btnToggle.classList.add('bg-red-600', 'hover:bg-red-500', 'shadow-red-500/30');

            statusDot.classList.remove('bg-red-500');
            statusDot.classList.add('bg-emerald-500', 'pulse');
            statusText.textContent = 'Harvester Działa';
            statusIndicator.classList.add('border-emerald-500/30');
        } else {
            btnToggle.textContent = 'URUCHOM ZBIERANIE';
            btnToggle.classList.add('bg-blue-600', 'hover:bg-blue-500', 'shadow-blue-500/30');
            btnToggle.classList.remove('bg-red-600', 'hover:bg-red-500', 'shadow-red-500/30');

            statusDot.classList.add('bg-red-500');
            statusDot.classList.remove('bg-emerald-500', 'pulse');
            statusText.textContent = 'Zatrzymany';
            statusIndicator.classList.remove('border-emerald-500/30');
        }
    };

    const API_BASE = (window.location.hostname === '127.0.0.1' || window.location.hostname === 'localhost') && window.location.port !== '8000'
        ? 'http://127.0.0.1:8000'
        : '';

    const fetchStats = async () => {
        try {
            const res = await fetch(`${API_BASE}/api/stats`);
            const data = await res.json();

            // Harvester Stats
            updateStatusUI(data.harvester.status);
            statMessages.textContent = data.harvester.messages_collected.toLocaleString();
            statRate.innerHTML = `${data.harvester.messages_per_sec.toFixed(1)} <span class="text-xs text-slate-500">/s</span>`;

            const pingMs = Math.round(data.harvester.ping * 1000);
            statPing.textContent = isRunning ? `${pingMs} ms` : '0 ms';
            if (pingMs > 200) statPing.className = 'text-lg font-semibold text-yellow-400';
            else statPing.className = 'text-lg font-semibold text-emerald-400';

            // Prices Update with Highlight Animation
            if (data.harvester.current_prices) {
                const currentUSDT = parseFloat(data.harvester.current_prices['BTCUSDT'] || 0).toFixed(2);
                if (priceBTCUSDT.textContent !== currentUSDT && currentUSDT !== "0.00") {
                    priceBTCUSDT.textContent = currentUSDT;
                    priceBTCUSDT.classList.remove('text-emerald-400');
                    void priceBTCUSDT.offsetWidth; // trigger reflow
                    priceBTCUSDT.classList.add('text-emerald-400', 'transition', 'duration-300');

                    if (bigPricePanel) bigPricePanel.textContent = currentUSDT;
                }

                const currentUSDC = parseFloat(data.harvester.current_prices['BTCUSDC'] || 0).toFixed(2);
                if (priceBTCUSDC.textContent !== currentUSDC && currentUSDC !== "0.00") {
                    priceBTCUSDC.textContent = currentUSDC;
                }
            }


            // Stream counts
            const countTrade = document.getElementById('countTrade');
            const countDepth = document.getElementById('countDepth');
            const countTicker = document.getElementById('countTicker');

            if (countTrade && data.harvester.stream_counts) countTrade.textContent = (data.harvester.stream_counts['trade'] || 0).toLocaleString();
            if (countDepth && data.harvester.stream_counts) countDepth.textContent = (data.harvester.stream_counts['depth'] || 0).toLocaleString();
            if (countTicker && data.harvester.stream_counts) countTicker.textContent = (data.harvester.stream_counts['bookTicker'] || 0).toLocaleString();

            // Storage Stats
            statDisk.innerHTML = `${data.storage.total_size_mb} <span class="text-slate-500 text-sm">MB</span>`;

            // Total records count
            if (data.storage.initial_count_done) {
                statTotalSaved.textContent = data.storage.total_saved_count.toLocaleString();
                calculatingIndicator.classList.add('hidden');
            } else {
                statTotalSaved.textContent = data.storage.total_saved_count.toLocaleString();
                calculatingIndicator.classList.remove('hidden');
                calculatingIndicator.classList.remove('opacity-0');
                calculatingIndicator.classList.add('animate-spin');
            }

            // Obliczanie zajętości bufora I/O w locie
            let totalQueued = 0;
            for (let key in data.storage.buffer_sizes) {
                totalQueued += data.storage.buffer_sizes[key];
            }

            statBufferText.textContent = `${totalQueued} na kolejce`;

            // Wizualizacja bufora (z zakładanym limitem dla UI jako 50k wpisów max)
            const percent = Math.min(100, (totalQueued / 50000) * 100);
            statBufferBar.style.width = `${percent}%`;

            // Zmiana koloru paska przy przeciążeniu
            if (percent > 80) statBufferBar.className = 'bg-red-500 h-2 rounded-full';
            else if (percent > 50) statBufferBar.className = 'bg-yellow-500 h-2 rounded-full';
            else statBufferBar.className = 'bg-purple-500 h-2 rounded-full transition-all duration-500';

            // Throughput widget
            const thr1s = document.getElementById('thr1sCount');
            const thr1minTotal = document.getElementById('thr1minTotal');
            const thr1minAvg = document.getElementById('thr1minAvg');
            const thr1hTotal = document.getElementById('thr1hTotal');
            const thr1hAvg = document.getElementById('thr1hAvg');
            if (thr1s && data.storage.throughput_last_1s !== undefined) {
                thr1s.textContent = data.storage.throughput_last_1s.toLocaleString();
                thr1minTotal.textContent = data.storage.throughput_last_1min_total.toLocaleString();
                thr1minAvg.textContent = data.storage.throughput_last_1min_avg_per_sec;
                thr1hTotal.textContent = data.storage.throughput_last_1h_total.toLocaleString();
                thr1hAvg.textContent = data.storage.throughput_last_1h_avg_per_sec;
            }

            // Logs
            const liveLogs = document.getElementById('liveLogs');
            if (liveLogs && data.harvester.recent_logs) {
                if (data.harvester.recent_logs.length > 0) {
                    liveLogs.innerHTML = data.harvester.recent_logs.map(log => {
                        if (log.includes('TRADE')) return `<div class="text-emerald-400 font-bold">${log}</div>`;
                        if (log.includes('DEPTH')) return `<div class="text-slate-500">${log}</div>`;
                        return `<div>${log}</div>`;
                    }).join('');
                } else {
                    liveLogs.innerHTML = '<div class="text-slate-500 italic">Oczekuję na wiadomości...</div>';
                }
            }

        } catch (e) {
            console.error('Błąd pobierania statystyk:', e);
            updateStatusUI('Stopped');
        }
    };

    const updateTFChange = async () => {
        if (!tfPicker || !priceChangeBadge) return;
        const tf = tfPicker.value;
        const labelText = tfPicker.options[tfPicker.selectedIndex].text;
        if (tfLabel) tfLabel.textContent = labelText;

        try {
            // Binance nie wspiera "1y" (1 year), więc pobieramy 12 świec z "1M" (1 miesiąc)
            let fetchTf = tf;
            let limit = 2;
            if (tf === '1y') {
                fetchTf = '1M';
                limit = 12;
            }

            const res = await fetch(`https://api.binance.com/api/v3/klines?symbol=BTCUSDT&interval=${fetchTf}&limit=${limit}`);
            const df = await res.json();

            if (!df || df.length === 0) return;

            const firstCandle = df[0];
            const openPrice = parseFloat(firstCandle[1]);

            let currentPrice = parseFloat(bigPricePanel.textContent.replace(/[^0-9.]/g, ''));
            if (isNaN(currentPrice) || currentPrice === 0) {
                currentPrice = parseFloat(df[df.length - 1][4]);
            }

            const change = currentPrice - openPrice;
            const changePercent = (change / openPrice) * 100;

            const sign = change >= 0 ? '+' : '';
            const colorClass = change >= 0 ? 'text-emerald-400 border-emerald-500/30 bg-emerald-500/10' : 'text-red-400 border-red-500/30 bg-red-500/10';
            const icon = change >= 0 ? '▲' : '▼';

            priceChangeBadge.className = `text-lg font-bold px-5 py-2 rounded-xl border shadow-inner flex items-center gap-2 ${colorClass}`;
            priceChangeBadge.innerHTML = `<span>${icon}</span> <span>${sign}${change.toFixed(2)} (${sign}${changePercent.toFixed(2)}%)</span>`;
        } catch (e) {
            console.error('Błąd pobierania klines:', e);
        }
    };

    if (tfPicker) {
        tfPicker.addEventListener('change', updateTFChange);
    }
    setInterval(updateTFChange, 5000); // Odśwież co 5s
    updateTFChange();

    btnToggle.addEventListener('click', async () => {
        const endpoint = isRunning ? '/api/stop' : '/api/start';
        await fetch(`${API_BASE}${endpoint}`);
        fetchStats();
    });

    // Start Polling API co 1 sekundę
    pollInterval = setInterval(fetchStats, 1000);
    fetchStats();

    // --- NEWS LOGIC ---
    const newsContainer = document.getElementById('newsContainer');
    const newsTabs = document.querySelectorAll('.news-tab');
    let currentNewsFilter = 'bullish';

    const loadNews = async (filter) => {
        if (!newsContainer) return;
        newsContainer.innerHTML = '<div class="text-center text-slate-500 py-8 italic animate-pulse">Ładowanie wiadomości...</div>';
        try {
            const res = await fetch(`${API_BASE}/api/news?filter=${filter}`);
            const data = await res.json();

            if (data.items && data.items.length > 0) {
                newsContainer.innerHTML = data.items.map(item => {
                    const date = new Date(item.pubDate).toLocaleString('pl-PL', { dateStyle: 'short', timeStyle: 'short' });
                    return `
                        <a href="${item.link}" target="_blank" class="block p-4 rounded-lg bg-slate-800/50 hover:bg-slate-700 transition border border-slate-700/50">
                            <h3 class="text-sm font-semibold text-slate-200 mb-2 leading-snug">${item.title}</h3>
                            <p class="text-[10px] text-slate-500 uppercase tracking-wider">${date}</p>
                        </a>
                    `;
                }).join('');
            } else {
                newsContainer.innerHTML = '<div class="text-center text-slate-500 py-8">Brak wiadomości dla tej kategorii.</div>';
            }
        } catch (e) {
            newsContainer.innerHTML = '<div class="text-center text-red-400 py-8">Błąd ładowania wiadomości.</div>';
        }
    };

    newsTabs.forEach(tab => {
        tab.addEventListener('click', (e) => {
            newsTabs.forEach(t => {
                t.classList.remove('bg-blue-600', 'text-white');
                t.classList.add('bg-slate-800', 'text-slate-400');
            });
            e.target.classList.remove('bg-slate-800', 'text-slate-400');
            e.target.classList.add('bg-blue-600', 'text-white');
            currentNewsFilter = e.target.dataset.filter;
            loadNews(currentNewsFilter);
        });
    });

    if (newsContainer) loadNews(currentNewsFilter);
    setInterval(() => loadNews(currentNewsFilter), 300000); // Odśwież co 5 minut

    // --- CALENDAR LOGIC ---
    const calendarContainer = document.getElementById('calendarContainer');
    const events = [
        { title: "Bitcoin Halving", date: "2028-04-15T00:00:00Z" },
        { title: "Mt. Gox Distribution Deadline", date: "2026-10-31T00:00:00Z" },
        { title: "US FOMC Rate Decision", date: "2026-03-18T18:00:00Z" },
        { title: "US CPI Release", date: "2026-03-11T13:30:00Z" }
    ];

    const updateCalendar = () => {
        if (!calendarContainer) return;
        const now = new Date();

        // Sort and map valid upcoming events
        const upcoming = events.map(ev => {
            const exDate = new Date(ev.date);
            const diff = exDate - now;
            return { ...ev, exDate, diff };
        }).filter(ev => ev.diff > 0).sort((a, b) => a.diff - b.diff);

        calendarContainer.innerHTML = upcoming.map(ev => {
            const days = Math.floor(ev.diff / (1000 * 60 * 60 * 24));
            const hours = Math.floor((ev.diff / (1000 * 60 * 60)) % 24);
            const isSoon = days < 7;

            return `
                <div class="flex items-center justify-between p-4 rounded-lg bg-slate-800/50 border border-slate-700/50">
                    <div>
                        <h3 class="text-sm font-semibold ${isSoon ? 'text-pink-400' : 'text-slate-200'} mb-1">${ev.title}</h3>
                        <p class="text-xs text-slate-500">${ev.exDate.toLocaleDateString('pl-PL')}</p>
                    </div>
                    <div class="text-right flex gap-3">
                        <div class="text-center">
                            <span class="block text-xl font-bold ${isSoon ? 'text-pink-400' : 'text-white'}">${days}</span>
                            <span class="text-[10px] text-slate-500 uppercase">Dni</span>
                        </div>
                        <div class="text-center">
                            <span class="block text-xl font-bold ${isSoon ? 'text-pink-400' : 'text-white'}">${hours}</span>
                            <span class="text-[10px] text-slate-500 uppercase">Godz.</span>
                        </div>
                    </div>
                </div>
            `;
        }).join('');
    };

    if (calendarContainer) {
        updateCalendar();
        setInterval(updateCalendar, 60000); // Update every minute
    }
});
