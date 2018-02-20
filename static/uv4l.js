/**
 * Created by chadwalalcehart on 1/27/18.
 * Adaption of uv4l WebRTC samples to receive only
 */

const uv4lPort = 9080; //This is determined by the uv4l configuration. 9080 is default set by uv4l-raspidisp-extras
let protocol = location.protocol === "https:" ? "wss:" : "ws:";
let signalling_server_address = location.hostname + ':' + uv4lPort;
let ws = new WebSocket(protocol + '//' + signalling_server_address + '/stream/webrtc');

let remoteVideo = null;   //make this global, initialize on document ready

let pc; //make peerConnection object global

//////////////////////////
/*** Peer Connection ***/

function startPeerConnection() {
    const pcConfig = {
        'iceServers': [{
            'urls': ['stun:stun.l.google.com:19302']
        }]
    };

    //Setup our peerConnection object
    pc = new RTCPeerConnection(pcConfig);

    pc.onicecandidate = (event) => {
        console.log('icecandidate event: ', event);
        if (event.candidate) {
            let candidate = {
                sdpMLineIndex: event.candidate.sdpMLineIndex,
                sdpMid: event.candidate.sdpMid,
                candidate: event.candidate.candidate
            };

            let req = {
                what: "addIceCandidate",
                data: JSON.stringify(candidate)
            };

            ws.send(JSON.stringify(req));

        } else {
            console.log('End of candidates.');
        }
    };

    pc.ontrack = (event) => {
        if (remoteVideo.srcObject !== event.streams[0]) {
            remoteVideo.srcObject = event.streams[0];
            remoteVideo.play();
            console.log('Remote stream added.');
        }
    };

    pc.onremovestream = (event) => console.log('Remote stream removed. Event: ', event);

    //Handle datachannel messages
    pc.ondatachannel = (event) => {
        console.log("onDataChannel()");
        datachannel = event.channel;

        event.channel.onopen = () => console.log("Data Channel opened");

        event.channel.onerror = (error) => console.error("Data Channel Error:", error);

        event.channel.onmessage = (event) => {
            //console.log("DataChannel Message:", event.data);
            processAiyData(JSON.parse(event.data));
        };

        event.channel.onclose = () => console.log("The Data Channel is Closed");
    };


    console.log('Created RTCPeerConnnection');

}

////////////////////////////////////
/*** Call signaling to start call and
 * handle ICE candidates ***/

function startCall() {

    //Initialize the peerConnection
    startPeerConnection();


    //Send the call commmand
    let req = {
        what: "call",
        options: {
            //ToDo: Figure out why Chrome mobile H.264 flag doesn't work
            force_hw_vcodec: true,
            vformat: 55
        }
    };

    ws.send(JSON.stringify(req));
    console.log("Initiating call request" + JSON.stringify(req));

}


//ToDo: Ask why no trickle??
function onIceCandidates(canidates) {
    for (candidate in canidates)
        console.log("Remote ICE candidate: " + candidate);
    let candidate = new RTCIceCandidate({
        sdpMLineIndex: candidate.sdpMLineIndex, //no label
        candidate: message.candidate
    });

    pc.addIceCandidate(candidate)
        .then(() => console.log("Added ICE candidate"),
            (err) => console.log("Error adding candidate"));
}

function onOffer(remoteSdp) {
    pc.setRemoteDescription(new RTCSessionDescription(remoteSdp))
        .then(() => console.log("setRemoteDescription complete"),
            (err) => console.error("Failed to setRemoteDescription: " + err));

    pc.createAnswer().then(
        (localSdp) => {
            pc.setLocalDescription(localSdp)
                .then(() => console.log("setLocalDescription complete"),
                    (err) => console.error("setLocalDescription error:" + err));

            let req = {
                what: "answer",
                data: JSON.stringify(localSdp)
            };
            ws.send(JSON.stringify(req));
            console.log("Sending local SDP: " + JSON.stringify(localSdp));
        },
        (error) =>
            console.log('Failed to create session description: ' + error.toString())
    );

    console.log("telling uv4l-server to generate IceCandidates");
    ws.send(JSON.stringify({what: "generateIceCandidates"}));

}


////////////////////////////////////
/*** Handle WebSocket messages ***/

function websocketEvents() {

    ws.onopen = function () {
        console.log("websocket open");

        startCall();

    };

    /*** Signaling logic ***/
    ws.onmessage = (event) => {
        let message = JSON.parse(event.data);
        console.log("message=" + JSON.stringify(message));
        //console.log("type=" + msg.type);

        if (message.what === 'undefined') {
            console.error("No websocket message");
            return;
        }

        switch (message.what) {
            case "offer":
                onOffer(JSON.parse(message.data));
                break;

            case "geticecandidate":
                onIceCandidates(message);
                break;
        }
    };

    ws.onerror = (error) => {
        console.error("Websocket error: " + error.toString());
    };

}

////////////////////////////////
/*** General control logic ***/


//Close & clean-up everything
function stop() {

    remoteVideo.src = '';
    if (pc) {
        pc.close();
        pc = null;
    }
    if (ws) {
        ws.close();
        ws = null;
    }
}


//Exit gracefully
window.onbeforeunload = function () {
    if (ws) {
        ws.send({log: 'closing browser'});
        ws.onclose = function () {
        }; // disable onclose handler first
        stop();
    }
};

//////////////////////////
/*** video handling ***/

document.addEventListener("DOMContentLoaded", (event) => {

    remoteVideo = document.querySelector('#remoteVideo');

    websocketEvents();

    remoteVideo.loadend = () => {
        remoteVideo.addEventListener('loadedmetadata', function () {
            console.log('Remote video videoWidth: ' + this.videoWidth +
                'px,  videoHeight: ' + this.videoHeight + 'px');
        });


        remoteVideo.onresize = function () {
            console.log('Remote video size changed to ' +
                remoteVideo.videoWidth + 'x' + remoteVideo.videoHeight);
        };
    };

});