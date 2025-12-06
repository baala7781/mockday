/**
 * AudioWorklet processor for converting Float32 audio samples to Int16 PCM
 * This is required for Deepgram Live API which expects raw PCM16 audio
 */
class PCM16Processor extends AudioWorkletProcessor {
  constructor() {
    super();
    this.bufferSize = 1024; // Buffer size for PCM chunks (reduced to prevent WebSocket buffer overflow)
    this.buffer = new Float32Array(this.bufferSize);
    this.bufferIndex = 0;
  }

  process(inputs, outputs, parameters) {
    const input = inputs[0];
    
    // Get the first channel (mono)
    if (!input || !input[0]) {
      return true; // Keep processor alive
    }

    const inputChannel = input[0]; // Float32Array from AudioContext

    // Convert Float32 to Int16 PCM and send chunks
    for (let i = 0; i < inputChannel.length; i++) {
      // Clamp to [-1, 1] range and convert to Int16 range [-32768, 32767]
      const sample = Math.max(-1, Math.min(1, inputChannel[i]));
      const int16Sample = sample < 0 ? sample * 0x8000 : sample * 0x7FFF; // Correct PCM16 conversion
      
      // Store in buffer
      this.buffer[this.bufferIndex++] = int16Sample;

      // When buffer is full, send it
      if (this.bufferIndex >= this.bufferSize) {
        // Convert Float32 buffer to Int16Array
        const int16Buffer = new Int16Array(this.bufferSize);
        for (let j = 0; j < this.bufferSize; j++) {
          int16Buffer[j] = Math.round(this.buffer[j]);
        }
        
        // Send PCM16 chunk to main thread
        this.port.postMessage(int16Buffer.buffer);
        
        // Reset buffer
        this.bufferIndex = 0;
      }
    }

    // Also send partial buffer if we have some data and input is ending
    // (This is less critical for streaming, but good for cleanup)

    return true; // Keep processor alive
  }
}

registerProcessor('pcm16-processor', PCM16Processor);

