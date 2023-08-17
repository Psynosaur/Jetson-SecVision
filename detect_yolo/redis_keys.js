let currentPage = 1;
const pageSize = 9; // You can change this to match your paging size
const tableBody = document.getElementById("tableBody");

const removeKey = (id, filePath, channel) => {
    fetch(`/removekey?id=${id}&path=${filePath}&channel=${channel}`, { method: 'DELETE' })
        .then((response) => response.json())
        .then((data) => {
            if (confirm(`Are you sure you want to remove id: ${id}`)) {
                if (data.success) {
                    alert(`${id} removed successfully! \n${data.item}`);
                    window.location.reload();
                } else {
                    alert('Error removing key!');
                }
            }
        });
};


const urlParams = new URLSearchParams(window.location.search);
const channel = urlParams.get('channel');
let page = urlParams.get('page');
function fetchData() {
    let description = ""
    if (page < 1) {
        page = 1;
    }
    async function fetchDataAsync(url) {
        const response = await fetch(url);
        const data = await response.json();

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
        data.forEach((item, index) => {
            const id = index + 1 + (page - 1) * pageSize;
            const imageUrl = `${item.path}frame.jpg`;
            let element = document.getElementById(index);
            element.src = imageUrl;
            element.alt = description;
            element.addEventListener("click", function () {
                removeKey(id, item.path, channel);
            });
        });
    }
    fetchDataAsync('/chaninfo?id=' + channel + '&page=' + page).then();
}

function renderChannelFrames(id, num) {
    let row = document.getElementById(id);
    for (let i = num; i < num + 3; i++) {
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
    return true;
};

function forwardPage() {
    let num = parseInt(page);
    num++;
    window.location.href = `/redis?channel=${channel}&page=${num}`;
}
function backPage() {
    let num = parseInt(page);
    if (page === 0 || page === 1) {
        return;
    }
    num--;
    window.location.href = `/redis?channel=${channel}&page=${num}`;
}
function forwardPage10() {
    let num = parseInt(page);
    num += 10;
    window.location.href = `/redis?channel=${channel}&page=${num}`;
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
    window.location.href = `/redis?channel=${channel}&page=${num}`;
}
document.addEventListener("DOMContentLoaded", function (event) {
    // Initial load
    renderChannelFrames('top', 0);
    renderChannelFrames('mid', 3);
    renderChannelFrames('bot', 6);
    fetchData();

    // loadData(currentPage);

});