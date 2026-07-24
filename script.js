// ============================================================
// 配置区（后续修改只动这里，无需理解下面代码）
// ============================================================

// 店铺基础信息
const CONFIG = {
    storeName: '书答水',                       // 店名
    slogan: '选择你想要的娱乐空间，提前锁定快乐', // 顶部副标题
    // PythonAnywhere 后端
    apiUrl: 'https://liuyt.pythonanywhere.com/api/booking',
    queryUrl: 'https://liuyt.pythonanywhere.com/api/occupied'
};

// 可预约项目列表（available: true 可约 / false 不可约并置灰）
const rooms = [
    {
        id: 'ktv',
        name: 'KTV 小包',
        icon: '🎤',
        desc: '私密小包间，适合 2-6 人欢唱。',
        price: '按位计费',
        unit: '每人 20 分钟',
        slotMin: 20,            // 每个时段 20 分钟
        available: true
    },
    {
        id: 'boardgame',
        name: '桌游中包',
        icon: '🎲',
        desc: '适合 6-12 人桌游、聚会，仅对外整租。',
        price: '整租',
        unit: '暂不开放按位预约',
        available: false
    },
    {
        id: 'party',
        name: '轰趴大包',
        icon: '🎉',
        desc: '适合 15-40 人派对、团建，仅对外整租。',
        price: '整租',
        unit: '暂不开放按位预约',
        available: false
    },
    {
        id: 'chess',
        name: '棋牌弈境',
        icon: '♟️',
        desc: '麻将、德州、棋类等休闲对弈空间。',
        price: '按位计费',
        unit: '每人 40 分钟',
        slotMin: 40,            // 每个时段 40 分钟
        available: true
    }
];

// 营业时段（来自预约表）：11:00 - 22:20，每 20 分钟一档
const SLOT_START = '11:00';   // 第一个时段起点
const SLOT_LAST_END = '22:20'; // 最后一个时段终点

function timeToMin(t) { const [h, m] = t.split(':').map(Number); return h * 60 + m; }
function minToTime(min) { const h = Math.floor(min / 60), m = min % 60; return String(h).padStart(2, '0') + ':' + String(m).padStart(2, '0'); }

// 按项目时段长度生成可选时间段（occupied 是已被占的时段列表）
function buildSlots(durationMin, occupied) {
    const start = timeToMin(SLOT_START);
    const end = timeToMin(SLOT_LAST_END);
    const occupiedSet = new Set(occupied || []);
    const out = [];
    for (let t = start; t + durationMin <= end + 0.001; t += 20) {
        const label = minToTime(t) + '—' + minToTime(t + durationMin);
        out.push({ value: label, label, disabled: occupiedSet.has(label) });
    }
    return out;
}

// ============================================================
// 以下为渲染与交互逻辑（一般无需改动）
// ============================================================

// 顶部店名 / 标语
document.getElementById('storeName').textContent = CONFIG.storeName;
document.getElementById('slogan').textContent = CONFIG.slogan;
document.title = `${CONFIG.storeName} · 预约订场`;

// 渲染房间列表
const roomList = document.getElementById('roomList');

function renderRooms() {
    roomList.innerHTML = rooms.map(room => {
        const disabledClass = room.available ? 'room-card--available' : 'room-card--disabled';
        const tagClass = room.available ? 'room-card__tag--available' : 'room-card__tag--disabled';
        const tagText = room.available ? '可预约' : '不可预约';
        const disabledMark = room.available ? '' : '<span class="disabled-watermark">暂不可约</span>';

        return `
            <article class="room-card ${disabledClass}" data-id="${room.id}">
                <div class="room-card__icon">${room.icon}</div>
                <div class="room-card__info">
                    <div class="room-card__top">
                        <h3 class="room-card__title">${room.name}</h3>
                        <span class="room-card__tag ${tagClass}">${tagText}</span>
                    </div>
                    <p class="room-card__desc">${room.desc}</p>
                    <div class="room-card__footer">
                        <span class="room-card__price">${room.price}</span>
                        <span class="room-card__hint">${room.unit}</span>
                    </div>
                </div>
                ${disabledMark}
            </article>
        `;
    }).join('');
}

renderRooms();

// 表单提交后重定向回来的提示
(function checkRedirect() {
    const p = new URLSearchParams(window.location.search);
    if (p.get('success') === '1') {
        history.replaceState({}, '', window.location.pathname);
        showToast('预约成功！我们会尽快联系你', 'success');
    } else if (p.get('error') === '1') {
        history.replaceState({}, '', window.location.pathname);
        showToast('提交失败，请重试', 'error');
    } else if (p.get('error') === 'missing') {
        history.replaceState({}, '', window.location.pathname);
        showToast('请填写电话和项目', 'error');
    }
})();

// 弹窗逻辑
const modal = document.getElementById('bookingModal');
const modalTitle = document.getElementById('modalTitle');
const modalClose = document.getElementById('modalClose');
const bookingForm = document.getElementById('bookingForm');

// ========== Toast 轻提示（替代 alert，更适合手机）==========
const toastEl = document.getElementById('toast');
let toastTimer = null;
function showToast(msg, type = 'info') {
    toastEl.textContent = msg;
    toastEl.className = `toast toast--show toast--${type}`;
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => { toastEl.className = 'toast'; }, 2200);
}

// ========== 自定义日期选择器（适配微信 X5 内核）==========
const dateInput = document.getElementById('date');
const dateSheet = document.getElementById('dateSheet');
const dateGrid = document.getElementById('dateGrid');
let selectedDate = '';

function buildDateGrid() {
    const weekdays = ['周日', '周一', '周二', '周三', '周四', '周五', '周六'];
    const today = new Date();
    let html = '';
    for (let i = 0; i < 14; i++) {
        const d = new Date(today);
        d.setDate(today.getDate() + i);
        const y = d.getFullYear();
        const m = String(d.getMonth() + 1).padStart(2, '0');
        const day = String(d.getDate()).padStart(2, '0');
        const val = `${y}-${m}-${day}`;
        const label = i === 0 ? '今天' : i === 1 ? '明天' : weekdays[d.getDay()];
        html += `<button type="button" class="date-cell" data-value="${val}">
                    <span class="date-cell__label">${label}</span>
                    <span class="date-cell__sub">${m}/${day}</span>
                 </button>`;
    }
    dateGrid.innerHTML = html;
}
buildDateGrid();

dateInput.addEventListener('click', () => dateSheet.classList.add('show'));
dateSheet.querySelector('.sheet__overlay').addEventListener('click', () => dateSheet.classList.remove('show'));
dateSheet.querySelector('.sheet__cancel').addEventListener('click', () => dateSheet.classList.remove('show'));

dateGrid.addEventListener('click', (e) => {
    const cell = e.target.closest('.date-cell');
    if (!cell) return;
    dateGrid.querySelectorAll('.date-cell').forEach(c => c.classList.remove('active'));
    cell.classList.add('active');
    selectedDate = cell.dataset.value;
});

document.getElementById('dateConfirm').addEventListener('click', () => {
    if (!selectedDate) { showToast('请先选择日期', 'error'); return; }
    dateInput.value = selectedDate;
    dateSheet.classList.remove('show');
});

// ========== 查询已占用时段 ==========
async function fetchOccupied(roomName, date) {
    try {
        const resp = await fetch(CONFIG.queryUrl + '?room=' + encodeURIComponent(roomName) + '&date=' + encodeURIComponent(date));
        const data = await resp.json();
        return data.occupied || [];
    } catch (e) { return []; }
}

// ========== 时段按钮渲染 ==========
let currentRoom = null;

function populateSlots(slots) {
    const container = document.getElementById('timeSlots');
    document.getElementById('time').value = '';
    container.innerHTML = '';
    slots.forEach(s => {
        const btn = document.createElement('button');
        btn.type = 'button';
        btn.className = 'time-slot' + (s.disabled ? ' time-slot--disabled' : '');
        btn.textContent = s.label;
        btn.disabled = s.disabled;
        if (!s.disabled) {
            btn.addEventListener('click', () => {
                container.querySelectorAll('.time-slot--active').forEach(b => b.classList.remove('time-slot--active'));
                btn.classList.add('time-slot--active');
                document.getElementById('time').value = s.value;
            });
        }
        container.appendChild(btn);
    });
}

function openModal(room) {
    currentRoom = room;
    modalTitle.textContent = '预约 ' + room.name;
    bookingForm.dataset.roomId = room.id;
    bookingForm.reset();

    const today = new Date();
    const y = today.getFullYear();
    const mm = String(today.getMonth() + 1).padStart(2, '0');
    const dd = String(today.getDate()).padStart(2, '0');
    const todayStr = y + '-' + mm + '-' + dd;
    document.getElementById('date').value = todayStr;
    selectedDate = todayStr;

    // 先显示弹窗，再异步加载时段
    modal.classList.add('show');
    document.getElementById('timeSlots').innerHTML = '<span style=\"color:#999;font-size:13px\">加载时段…</span>';

    loadSlots(room, todayStr);
}

async function loadSlots(room, dateStr) {
    const occupied = await fetchOccupied(room.name, dateStr);
    populateSlots(buildSlots(room.slotMin || 20, occupied));
}

function closeModal() {
    modal.classList.remove('show');
    bookingForm.reset();
    delete bookingForm.dataset.roomId;
    currentRoom = null;
    document.getElementById('timeSlots').innerHTML = '';
}

modalClose.addEventListener('click', closeModal);
modal.querySelector('.modal__overlay').addEventListener('click', closeModal);

// 日期确定后刷新时段
document.getElementById('dateConfirm').addEventListener('click', async () => {
    if (!selectedDate) { showToast('请先选择日期', 'error'); return; }
    document.getElementById('date').value = selectedDate;
    dateSheet.classList.remove('show');
    if (currentRoom) {
        document.getElementById('timeSlots').innerHTML = '<span style=\"color:#999;font-size:13px\">加载时段…</span>';
        document.getElementById('time').value = '';
        await loadSlots(currentRoom, selectedDate);
    }
});

// 点击房间卡 → 弹窗
roomList.addEventListener('click', async (e) => {
    const card = e.target.closest('.room-card');
    if (!card) return;
    const room = rooms.find(item => item.id === card.dataset.id);
    if (!room) return;
    if (!room.available) { showToast('该项目暂不开放预约', 'error'); return; }
    await openModal(room);
});

// ========== 表单提交 ==========
function submitBooking(data) {
    const form = document.createElement('form');
    form.method = 'POST';
    form.action = CONFIG.apiUrl;
    form.style.display = 'none';
    const fields = { code: data.code || '', roomName: data.roomName || '', date: data.date || '', time: data.time || '', remark: data.remark || '' };
    for (const [k, v] of Object.entries(fields)) {
        const input = document.createElement('input');
        input.type = 'hidden'; input.name = k; input.value = v;
        form.appendChild(input);
    }
    document.body.appendChild(form);
    form.submit();
}

bookingForm.addEventListener('submit', (e) => {
    e.preventDefault();
    const code = (document.getElementById('code').value || '').trim();
    const date = document.getElementById('date').value;
    const time = document.getElementById('time').value;

    if (!/^\d{4}$/.test(code)) { showToast('请输入4位数字手环编号', 'error'); return; }
    if (!date) { showToast('请选择预约日期', 'error'); return; }
    if (!time) { showToast('请选择时段', 'error'); return; }

    const room = rooms.find(r => r.id === bookingForm.dataset.roomId);
    submitBooking({
        code: code,
        roomName: room ? room.name : '',
        date: date,
        time: time,
        remark: (document.getElementById('remark').value || '').trim()
    });
});
