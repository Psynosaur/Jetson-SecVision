function renderIndexChannelFrames(id, num) {
    let row = document.getElementById(id);
    for (i = num; i < num + 3; i++) {
        if (i < 8) {
            row.innerHTML +=
            `
                <div class="column is-one-third">
                    <div class="card">
                        <div class="card-image">
                            <figure class="image is-16by9">
                                <a href="/channel?id=${i + 1}01">
                                    <img src="/channel?id=${i + 1}01" alt="Front Lawn">
                                </a>
                            </figure>
                        </div>

                    </div>
                </div>
            `
        }
    }
};
document.onload = renderIndexChannelFrames('top', 0);
document.onload = renderIndexChannelFrames('mid', 3);
document.onload = renderIndexChannelFrames('bot', 6);
