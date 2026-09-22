// frontend/src/utils/soundEffects.ts

/**
 * Tactile Chess Board Sound Synthesizer (Web Audio API)
 *
 * Generates organic, high-fidelity tactile wooden chess clicks, captures,
 * checks, castles, and match conclusions without any external audio asset dependencies.
 */

class ChessSoundSynthesizer {
  private ctx: AudioContext | null = null;
  private isMuted: boolean = false;
  private isInitialized: boolean = false;

  constructor() {
    // Lazy initialization on first user interaction to comply with browser autoplay policies
    if (typeof window !== 'undefined') {
      const initAudio = () => {
        this.ensureContext();
        window.removeEventListener('pointerdown', initAudio);
        window.removeEventListener('keydown', initAudio);
      };
      window.addEventListener('pointerdown', initAudio, { once: true });
      window.addEventListener('keydown', initAudio, { once: true });
    }
  }

  private ensureContext(): AudioContext | null {
    if (typeof window === 'undefined') return null;
    if (!this.ctx) {
      const AudioCtx = window.AudioContext || (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
      if (AudioCtx) {
        this.ctx = new AudioCtx();
        this.isInitialized = true;
      }
    }
    if (this.ctx && this.ctx.state === 'suspended') {
      this.ctx.resume().catch(() => {});
    }
    return this.ctx;
  }

  public setMuted(muted: boolean): void {
    this.isMuted = muted;
  }

  public getMuted(): boolean {
    return this.isMuted;
  }

  /**
   * Helper to create a micro-noise impulse for the tactile transient click
   */
  private createClickImpulse(ctx: AudioContext, startTime: number, volume: number = 0.08) {
    const bufferSize = Math.floor(ctx.sampleRate * 0.008); // 8ms burst
    const buffer = ctx.createBuffer(1, bufferSize, ctx.sampleRate);
    const data = buffer.getChannelData(0);
    for (let i = 0; i < bufferSize; i++) {
      data[i] = (Math.random() * 2 - 1) * Math.exp(-i / (bufferSize * 0.3));
    }

    const noise = ctx.createBufferSource();
    noise.buffer = buffer;

    const filter = ctx.createBiquadFilter();
    filter.type = 'bandpass';
    filter.frequency.setValueAtTime(1600, startTime);
    filter.Q.setValueAtTime(1.5, startTime);

    const gain = ctx.createGain();
    gain.gain.setValueAtTime(volume, startTime);
    gain.gain.exponentialRampToValueAtTime(0.0001, startTime + 0.008);

    noise.connect(filter);
    filter.connect(gain);
    gain.connect(ctx.destination);

    noise.start(startTime);
  }

  /**
   * Standard piece move: Crisp wooden board tap
   */
  public playMove(): void {
    if (this.isMuted) return;
    const ctx = this.ensureContext();
    if (!ctx) return;

    const now = ctx.currentTime;

    // 1. Transient click
    this.createClickImpulse(ctx, now, 0.07);

    // 2. Resonant wood body (Triangle wave frequency drop 320Hz -> 110Hz)
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();

    osc.type = 'triangle';
    osc.frequency.setValueAtTime(320, now);
    osc.frequency.exponentialRampToValueAtTime(110, now + 0.04);

    gain.gain.setValueAtTime(0.18, now);
    gain.gain.exponentialRampToValueAtTime(0.0001, now + 0.045);

    osc.connect(gain);
    gain.connect(ctx.destination);

    osc.start(now);
    osc.stop(now + 0.05);
  }

  /**
   * Piece capture: Deep, punchy acoustic snap
   */
  public playCapture(): void {
    if (this.isMuted) return;
    const ctx = this.ensureContext();
    if (!ctx) return;

    const now = ctx.currentTime;

    // 1. Heavier transient snap
    this.createClickImpulse(ctx, now, 0.14);

    // 2. Dual-layer acoustic impact
    const osc1 = ctx.createOscillator();
    const osc2 = ctx.createOscillator();
    const gain = ctx.createGain();

    osc1.type = 'triangle';
    osc1.frequency.setValueAtTime(240, now);
    osc1.frequency.exponentialRampToValueAtTime(80, now + 0.06);

    osc2.type = 'sine';
    osc2.frequency.setValueAtTime(140, now);
    osc2.frequency.exponentialRampToValueAtTime(60, now + 0.07);

    gain.gain.setValueAtTime(0.25, now);
    gain.gain.exponentialRampToValueAtTime(0.0001, now + 0.075);

    osc1.connect(gain);
    osc2.connect(gain);
    gain.connect(ctx.destination);

    osc1.start(now);
    osc2.start(now);
    osc1.stop(now + 0.08);
    osc2.stop(now + 0.08);
  }

  /**
   * Check move: Bright harmonic wooden click with alert chime ping
   */
  public playCheck(): void {
    if (this.isMuted) return;
    const ctx = this.ensureContext();
    if (!ctx) return;

    const now = ctx.currentTime;

    // 1. Crisp wood impact
    this.playMove();

    // 2. Resonant high chime alert ping (784Hz - G5)
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();

    osc.type = 'sine';
    osc.frequency.setValueAtTime(784, now + 0.015);

    gain.gain.setValueAtTime(0.12, now + 0.015);
    gain.gain.exponentialRampToValueAtTime(0.0001, now + 0.16);

    osc.connect(gain);
    gain.connect(ctx.destination);

    osc.start(now + 0.015);
    osc.stop(now + 0.18);
  }

  /**
   * Castling: Rapid double slide-tap
   */
  public playCastle(): void {
    if (this.isMuted) return;
    const ctx = this.ensureContext();
    if (!ctx) return;

    const now = ctx.currentTime;

    // King step
    this.createClickImpulse(ctx, now, 0.06);
    const osc1 = ctx.createOscillator();
    const gain1 = ctx.createGain();
    osc1.type = 'triangle';
    osc1.frequency.setValueAtTime(290, now);
    osc1.frequency.exponentialRampToValueAtTime(120, now + 0.035);
    gain1.gain.setValueAtTime(0.14, now);
    gain1.gain.exponentialRampToValueAtTime(0.0001, now + 0.04);
    osc1.connect(gain1);
    gain1.connect(ctx.destination);
    osc1.start(now);
    osc1.stop(now + 0.045);

    // Rook slide-hop 55ms later
    const tap2Time = now + 0.055;
    this.createClickImpulse(ctx, tap2Time, 0.07);
    const osc2 = ctx.createOscillator();
    const gain2 = ctx.createGain();
    osc2.type = 'triangle';
    osc2.frequency.setValueAtTime(340, tap2Time);
    osc2.frequency.exponentialRampToValueAtTime(140, tap2Time + 0.035);
    gain2.gain.setValueAtTime(0.15, tap2Time);
    gain2.gain.exponentialRampToValueAtTime(0.0001, tap2Time + 0.04);
    osc2.connect(gain2);
    gain2.connect(ctx.destination);
    osc2.start(tap2Time);
    osc2.stop(tap2Time + 0.045);
  }

  /**
   * Game Concluded / Checkmate: Resonant cadence
   */
  public playGameOver(): void {
    if (this.isMuted) return;
    const ctx = this.ensureContext();
    if (!ctx) return;

    const now = ctx.currentTime;

    // Harmonic warm bell gong (C4: 261.63Hz + G4: 392.00Hz)
    [261.63, 392.00].forEach((freq) => {
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();

      osc.type = 'sine';
      osc.frequency.setValueAtTime(freq, now);

      gain.gain.setValueAtTime(0.15, now);
      gain.gain.exponentialRampToValueAtTime(0.0001, now + 0.55);

      osc.connect(gain);
      gain.connect(ctx.destination);

      osc.start(now);
      osc.stop(now + 0.60);
    });
  }
}

export const soundEffects = new ChessSoundSynthesizer();
