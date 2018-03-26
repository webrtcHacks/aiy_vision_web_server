/**
 * Created by chadwallacehart on 1/27/18.
 * Setup and draw boxes on a canvas
 * Written for webrtcHacks - https://webrtchacks.com
 */

/*exported processAiyData*/


//Video element selector
let v = document.getElementById("remoteVideo");

//for starting events
let isPlaying = false,
    gotMetadata = false;

//Canvas setup

//create a canvas for drawing object boundaries
let drawCanvas = document.createElement('canvas');
document.body.appendChild(drawCanvas);
let drawCtx = drawCanvas.getContext("2d");

let lastSighting = null;

//Convert RGB color integer values to hex
function toHex(n) {
    if (n < 256) {
        return Math.abs(n)
            .toString(16);
    }
    return 0;
}

//draw boxes and labels on each detected object
function drawBox(x, y, width, height, label, color) {

    if (color)
        drawCtx.strokeStyle = drawCtx.fillStyle = '#' + toHex(color.r) + toHex(color.g) + toHex(color.b);

    let cx = x * drawCanvas.width;
    let cy = y * drawCanvas.height;
    let cWidth = (width * drawCanvas.width) - x;
    let cHeight = (height * drawCanvas.height) - y;

    drawCtx.fillText(label, cx + 5, cy - 10);
    drawCtx.strokeRect(cx, cy, cWidth, cHeight);

}


//Main function to export
function processAiyData(result) {
    console.log(result);

    lastSighting = Date.now();

    //clear the previous drawings
    drawCtx.clearRect(0, 0, drawCanvas.width, drawCanvas.height);

    result.objects.forEach((item, itemNum) => {

        let label;

        switch (item.name) {
            case "face": {
                label = "Face: " + Math.round(item.score * 100) + "%" + " Joy: " + Math.round(item.joy * 100) + "%";
                let color = {
                    r: Math.round(item.joy * 255),
                    g: 70,
                    b: Math.round((1 - item.joy) * 255)
                };

                drawBox(item.x, item.y, item.width, item.height, label, color);
                break;
            }
            case "object": {
                label = item.class_name + " - " + Math.round(item.score * 100) + "%";
                drawBox(item.x, item.y, item.width, item.height, label);
                break;
            }
            case "class": {
                label = item.class_name + " - " + Math.round(item.score * 100) + "%";
                drawCtx.fillText(label, 20, 20 * (itemNum + 1));
                break;
            }
            default: {
                console.log("I don't know what that AIY Vision server response was");
            }
        }
    });

}


//Start object detection
function setupCanvas() {

    console.log("Ready to draw");

    //Set canvas sizes based on input video
    drawCanvas.width = v.videoWidth;
    drawCanvas.height = v.videoHeight;

    //Some styles for the drawCanvas
    drawCtx.lineWidth = 8;
    drawCtx.strokeStyle = "cyan";
    drawCtx.font = "20px Verdana";
    drawCtx.fillStyle = "cyan";

    //if no updates in the last 2 seconds then clear the canvas
    setInterval(() => {
        if (Date.now() - lastSighting > 1000)
            drawCtx.clearRect(0, 0, drawCanvas.width, drawCanvas.height);
    }, 500)

}

//Starting events

//check if metadata is ready - we need the video size
v.onloadedmetadata = () => {
    console.log("video metadata ready");
    gotMetadata = true;
    if (isPlaying)
        setupCanvas();
};

//see if the video has started playing
v.onplaying = () => {
    console.log("video playing");
    isPlaying = true;
    if (gotMetadata) {
        setupCanvas();
    }
};

