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
let remoteVideo = null;
let pc,
    dataChannel;

//////////////////////////
/*** Peer Connection ***/

function setupPeerConnection() {
    const pcConfig = {
        iceServers: [{
            urls: [
                //"stun:stun.l.google.com:19302",
                "stun:" + signalling_server_address + ":3478"
            ]
        }]
    };

    //Setup our peerConnection object
    pc = new RTCPeerConnection(pcConfig);

    //Start video
    pc.ontrack = (event) => {
        if (remoteVideo.srcObject !== event.streams[0]) {
            remoteVideo.srcObject = event.streams[0];
            remoteVideo.play()
                .then(() => console.log('Remote stream added.'));
        }
    };

    pc.onremovestream = (event) => {
        console.log('Remote stream removed. Event: ', event);
        remoteVideo.stop();
    };

    //Handle datachannel messages
    pc.ondatachannel = (event) => {

        dataChannel = event.channel;

        dataChannel.onopen = () => console.log("Data Channel opened");

        dataChannel.onerror = (err) => console.error("Data Channel Error:", err);

        dataChannel.onmessage = (event) => {
            //console.log("DataChannel Message:", event.data);
            processAiyData(JSON.parse(event.data));
        };

        dataChannel.onclose = () => console.log("The Data Channel is Closed");
    };

    console.log('Created RTCPeerConnnection');

}

////////////////////////////////////
/*** Call signaling to start call and
 * handle ICE candidates ***/

function startCall() {

    //Initialize the peerConnection
    setupPeerConnection();

    //Send the call commmand
    let req = {
        what: "call",
        options: {
            force_hw_vcodec: true,
            vformat: 55
        }
    };

    ws.send(JSON.stringify(req));
    console.log("Initiating call request" + JSON.stringify(req));

}

//Process incoming ICE candidates
//UV4L does not do Trickle-ICE and sends all candidates at once
//in a format that adapter.js doesn't like, so regenerate
function onIceCandidates(remoteCandidates) {

    function onAddIceCandidateSuccess() {
        console.log("Successfully added ICE candidate")
    }

    function onAddIceCandidateError(err) {
        console.error("Failed to add candidate: " + err)
    }

    remoteCandidates.forEach((candidate) => {
        let generatedCandidate = new RTCIceCandidate({
            sdpMLineIndex: candidate.sdpMLineIndex,
            candidate: candidate.candidate,
            sdpMid: candidate.sdpMid
        });
        console.log("Created ICE candidate: " + JSON.stringify(generatedCandidate));
        pc.addIceCandidate(generatedCandidate)
            .then(onAddIceCandidateSuccess, onAddIceCandidateError);
    });
}

//Handle Offer/Answer exchange
function offerAnswer(remoteSdp) {

    //Start the answer by setting the remote SDP
    pc.setRemoteDescription(new RTCSessionDescription(remoteSdp))
        .then(() => {
                console.log("setRemoteDescription complete");

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
            },
            (err) => console.error("Failed to setRemoteDescription: " + err));

    //Now ask for ICE candidates
    console.log("telling uv4l-server to generate IceCandidates");
    ws.send(JSON.stringify({what: "generateIceCandidates"}));

}


////////////////////////////////////
/*** Handle WebSocket messages ***/

function websocketEvents() {

    ws.onopen = () => {
        console.log("websocket open");

        startCall();

    };

    /*** Signaling logic ***/
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

            case "iceCandidates":
                onIceCandidates(JSON.parse(message.data));
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

    remoteVideo = document.querySelector('#remoteVideo');

    websocketEvents();

    remoteVideo.loadend = () => {
        remoteVideo.addEventListener('loadedmetadata', () => {
            console.log('Remote video videoWidth: ' + this.videoWidth +
                'px,  videoHeight: ' + this.videoHeight + 'px');
        });


        remoteVideo.onresize = () => {
            console.log('Remote video size changed to ' +
                remoteVideo.videoWidth + 'x' + remoteVideo.videoHeight);
        };
    };

});