function renderChannelFrames(id, num) {
    let row = document.getElementById(id);
    for (i = num; i < num + 3; i++) {
        row.innerHTML +=
            `
                <div class="column">
                    <div class="card">
                        <div class="card-image">
                            <figure class="image is-16by9">
                                <a target="_blank" id="p${i}">
                                    <img width="640" height="360" id=${i}>
                                </a>
                            </figure>
                        </div>
                    </div>
                </div>
            `
    }
};
const urlParams = new URLSearchParams(window.location.search);
const channel = urlParams.get('channel');
const page = urlParams.get('page');
function fetchData() {
    let description = ""
    if (page < 1) {
        page = 1;
    }
    async function fetchDataAsync(url) {
        const response = await fetch(url);
        const data = await response.json();
        let idx = 0

        switch (channel) {
            case '101':
                description = "Front Lawn"
                break;
            case '201':
                description = "Front Door"
                break;
            case '301':
                description = "Driveway"
                break;
            case '401':
                description = "Side Gate"
                break;
            case '501':
                description = "Courtyard"
                break;
            case '601':
                description = "Garage Gate"
                break;
            case '701':
                description = "Back Lawn"
                break;
            case '801':
                description = "Pool Area"
                break;
        }
        data.forEach(obj => {
            Object.entries(obj).forEach(([key, value]) => {
                if (key == 'path') {
                    document.getElementById(idx).src = value + 'frame.jpg';
                    document.getElementById(idx).alt = description;
                    let piclink = "p" + idx;
                    document.getElementById(piclink).href = value + 'frame.jpg';
                    idx = idx + 1;
                }
            });
        });
    }
    fetchDataAsync('/chaninfo?id=' + channel + '&page=' + page);
}
document.onload = renderChannelFrames('top', 0);
document.onload = renderChannelFrames('mid', 3);
document.onload = renderChannelFrames('bot', 6);
document.onload = fetchData();
document.onload = function BottomButs() {
    let touchstartX = 0
    let touchendX = 0

    const slider = document.getElementById('slider')

    function handleGesture() {
        if (touchendX < touchstartX) backPage()
        if (touchendX > touchstartX) forwardPage()
    }

    slider.addEventListener('touchstart', e => {
        touchstartX = e.changedTouches[0].screenX
    })

    slider.addEventListener('touchend', e => {
        touchendX = e.changedTouches[0].screenX
        handleGesture()
    })
}
function forwardPage() {
    let num = parseInt(page);
    num++;
    let uri = `/history?channel=${channel}&page=${num}`;
    window.location.href = uri;
}
function backPage() {
    let num = parseInt(page);
    if (page == 0 || page == 1) {
        return;
    }
    num--;
    let uri = `/history?channel=${channel}&page=${num}`;
    window.location.href = uri;
}
function forwardPage10() {
    let num = parseInt(page);
    num += 10;
    let uri = `/history?channel=${channel}&page=${num}`;
    window.location.href = uri;
}
function backPage10() {
    let num = parseInt(page);
    num -= 10;
    if (page === 0) {
        page = 1;
        return;
    }
    if (page < 10) {
        return;
    }
    let uri = `/history?channel=${channel}&page=${num}`;
    window.location.href = uri;
}