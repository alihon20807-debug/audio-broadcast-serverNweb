class RecorderProcessor extends AudioWorkletProcessor {
    constructor() {
        super();
    }

    process(inputs, outputs, parameters) {
        const input = inputs[0];
        // input[0] is left channel, input[1] is right channel
        if (input.length > 0) {
            const left = input[0];
            const right = input[1] || left; // Fallback to mono if only one channel
            
            // Interleave channels for the test mixing engine
            const interleaved = new Float32Array(left.length * 2);
            for (let i = 0; i < left.length; i++) {
                interleaved[i * 2] = left[i];
                interleaved[i * 2 + 1] = right[i];
            }
            
            // Send the interleaved chunk back to the main thread
            // This is safer than ScriptProcessor because the capture itself 
            // is never interrupted by main thread jank.
            this.port.postMessage(interleaved);
        }
        return true;
    }
}

registerProcessor('recorder-worker', RecorderProcessor);
