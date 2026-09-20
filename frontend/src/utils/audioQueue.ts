
import type { DialogueTurn } from '../types/broadcast';

type ActiveSpeakerCallback = (speaker: 'HOST' | 'ANALYST' | null, turn: DialogueTurn | null) => void;

class RadioAudioEngine {
  private queue: DialogueTurn[] = [];
  private currentAudio: HTMLAudioElement | null = null;
  private isPlaying = false;
  private isMuted = false;
  private onSpeakerChange: ActiveSpeakerCallback | null = null;

  constructor() {
    // Lazy initialization happens after first user gesture
  }

  public setSpeakerCallback(cb: ActiveSpeakerCallback) {
    this.onSpeakerChange = cb;
  }

  public setMuted(muted: boolean) {
    this.isMuted = muted;
    if (this.currentAudio) {
      this.currentAudio.muted = muted;
    }
  }

  public enqueueTurns(turns: DialogueTurn[]) {
    for (const turn of turns) {
      if (turn.audio_url) {
        this.queue.push(turn);
      }
    }
    if (!this.isPlaying) {
      this.playNext();
    }
  }

  public interrupt() {
    // 1. Immediately kill current audio element
    if (this.currentAudio) {
      this.currentAudio.pause();
      this.currentAudio.src = '';
      this.currentAudio = null;
    }
    // 2. Dump all pending standard priority audio
    this.queue = [];
    this.isPlaying = false;
    if (this.onSpeakerChange) {
      this.onSpeakerChange(null, null);
    }
  }

  private async playNext() {
    if (this.queue.length === 0) {
      this.isPlaying = false;
      if (this.onSpeakerChange) {
        this.onSpeakerChange(null, null);
      }
      return;
    }

    this.isPlaying = true;
    const turn = this.queue.shift()!;
    const audioUrl = turn.audio_url?.startsWith('http')
      ? turn.audio_url
      : `http://localhost:8000${turn.audio_url}`;

    try {
      const audio = new Audio(audioUrl);
      this.currentAudio = audio;
      audio.muted = this.isMuted;

      if (this.onSpeakerChange) {
        this.onSpeakerChange(turn.speaker, turn);
      }

      audio.onended = () => {
        this.currentAudio = null;
        this.playNext();
      };

      audio.onerror = () => {
        console.warn(`Could not play audio track: ${audioUrl}`);
        this.currentAudio = null;
        this.playNext();
      };

      await audio.play();
    } catch (err) {
      console.warn('Playback error or user gesture required:', err);
      this.playNext();
    }
  }
}

export const radioEngine = new RadioAudioEngine();