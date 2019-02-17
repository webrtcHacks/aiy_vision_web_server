/**
 * Created by chadwalalcehart on 1/27/18.
 * Adaption of uv4l WebRTC samples to receive only
 */

/*global processAiyData:false*/

const uv4lPort = 9080; //This is determined by the uv4l configuration. 9080 is default set by uv4l-raspidisp-extras
const protocol = location.protocol === "https:" ? "wss:" : "ws:";
const signalling_server_address = location.hostname;
let ws = new WebSocket(protocol + '//' + signalling_server_address + ':' + uv4lPort + '/stream/webrtc');

//Global vars
let remotePc = false;
let pc,
    dataChannel;
let iceCandidates = [];
const remoteVideo = document.querySelector('#remoteVideo');


////////////////////////////////////////
/*** Peer Connection Event Handlers ***/

function gotRemoteStream(e) {
    if (remoteVideo.srcObject !== e.streams[0]) {
        remoteVideo.srcObject = e.streams[0];
        console.log('Received remote stream');
    }
}

function gotDataChannel(event) {
    console.log("Data Channel opened");
    let receiveChannel = event.channel;
    receiveChannel.addEventListener('message', event => processAiyData(JSON.parse(event.data)));
    receiveChannel.addEventListener('error', err => console.error("DataChannel Error:", err));
    receiveChannel.addEventListener('close', () => console.log("The DataChannel is closed"));
}

////////////////////////////////////
/*** Call signaling to start call and
 * handle ICE candidates ***/

function startCall() {

    const pcConfig = {
        iceServers: [{
            urls: ["stun:" + signalling_server_address + ":3478"]
        }]
    };

    //Setup our peerConnection object
    pc = new RTCPeerConnection(pcConfig);

    pc.addEventListener('track', gotRemoteStream);
    pc.addEventListener('datachannel', gotDataChannel);

    //Send the call commmand
    let req = {
        what: "call",
        options: {
            force_hw_vcodec: true,
            vformat: 55,
            trickle_ice: true
        }
    };

    ws.send(JSON.stringify(req));
    console.log("Initiating call request" + JSON.stringify(req));

}

//Process incoming ICE candidates
// in a format that adapter.js doesn't like, so regenerate
function addIceCandidate(candidate) {

    function onAddIceCandidateSuccess() {
        console.log("Successfully added ICE candidate")
    }

    function onAddIceCandidateError(err) {
        console.error("Failed to add candidate: " + err)
    }

    let generatedCandidate = new RTCIceCandidate({
        sdpMLineIndex: candidate.sdpMLineIndex,
        candidate: candidate.candidate,
        sdpMid: candidate.sdpMid
    });
    //console.log("Created ICE candidate: " + JSON.stringify(generatedCandidate));

    //Hold on to them in case the remote PeerConnection isn't ready
    iceCandidates.push(generatedCandidate);

    //Add the generated candidates when the remote PeerConnection is ready
    if (remotePc) {
        iceCandidates.forEach((candidate) =>
            pc.addIceCandidate(candidate)
                .then(onAddIceCandidateSuccess, onAddIceCandidateError)
        );
        console.log("Added " + iceCandidates.length + " remote candidate(s)");
        iceCandidates = [];
    }
}

//Handle Offer/Answer exchange
function offerAnswer(remoteSdp) {

    //Start the answer by setting the remote SDP
    pc.setRemoteDescription(new RTCSessionDescription(remoteSdp))
        .then(() => {
                remotePc = true;
                console.log("setRemoteDescription complete")
            },
            (err) => console.error("Failed to setRemoteDescription: " + err));


    //Create the local SDP
    pc.createAnswer()
        .then(
            (localSdp) => {
                pc.setLocalDescription(localSdp)
                    .then(() => {
                            console.log("setLocalDescription complete");

                            //send the answer
                            let req = {
                                what: "answer",
                                data: JSON.stringify(localSdp)
                            };
                            ws.send(JSON.stringify(req));
                            console.log("Sent local SDP: " + JSON.stringify(localSdp));

                        },
                        (err) => console.error("setLocalDescription error:" + err));
            },
            (err) =>
                console.log('Failed to create session description: ' + err.toString())
        );

}


////////////////////////////////////
/*** Handle WebSocket messages ***/

function websocketEvents() {

    /*** Signaling logic ***/
    ws.onopen = () => {
        console.log("websocket open");

        startCall();
    };

    ws.onmessage = (event) => {
        let message = JSON.parse(event.data);
        console.log("Incoming message:" + JSON.stringify(message));

        if (!message.what) {
            console.error("Websocket message not defined");
            return;
        }

        switch (message.what) {

            case "offer":
                offerAnswer(JSON.parse(message.data));
                break;

            case "iceCandidate":
                if (!message.data) {
                    console.log("Ice Gathering Complete");
                } else
                    addIceCandidate(JSON.parse(message.data));
                break;

            //ToDo: Ask about this - I can't get this message to show
            case "iceCandidates":
                let candidates = JSON.parse(message.data);
                candidates.forEach((candidate) =>
                    addIceCandidate(JSON.parse(candidate)));
                break;

            default:
                console.warn("Unhandled websocket message: " + JSON.stringify(message))
        }
    };

    ws.onerror = (err) => {
        console.error("Websocket error: " + err.toString());
    };

    ws.onclose = () => {
        console.log("Websocket closed.");
    };


}

////////////////////////////////
/*** General control logic ***/

//Exit gracefully
window.onbeforeunload = () => {
    remoteVideo.src = '';

    if (pc) {
        pc.close();
        pc = null;
    }

    if (ws) {
        ws.send({log: 'closing browser'});
        ws.send(JSON.stringify({what: "hangup"}));
        ws.close();
        ws = null;
    }
};

//////////////////////////
/*** video handling ***/

document.addEventListener("DOMContentLoaded", () => {

    websocketEvents();

    remoteVideo.addEventListener('loadedmetadata', function () {
        console.log(`Remote video videoWidth: ${this.videoWidth}px,  videoHeight: ${this.videoHeight}px`);
    });

    remoteVideo.addEventListener('resize', () => {
        console.log(`Remote video size changed to ${remoteVideo.videoWidth}x${remoteVideo.videoHeight}`);
    });

});