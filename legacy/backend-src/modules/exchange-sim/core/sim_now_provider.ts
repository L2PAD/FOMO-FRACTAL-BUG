/**
 * Simulation Now Provider
 * =======================
 * 
 * Replaces Date.now() for all services during simulation.
 * This allows the system to "think" it's running on a historical date.
 */

import { SimNowProvider } from '../exchange_sim.types.js';

class SimulatedNowProvider implements SimNowProvider {
  private currentDate: Date = new Date();
  private isSimMode: boolean = false;
  
  now(): Date {
    if (this.isSimMode) {
      return new Date(this.currentDate);
    }
    return new Date();
  }
  
  set(date: Date): void {
    this.currentDate = new Date(date);
    this.isSimMode = true;
  }
  
  reset(): void {
    this.isSimMode = false;
    this.currentDate = new Date();
  }
  
  isSimulating(): boolean {
    return this.isSimMode;
  }
  
  // For services that need timestamp
  timestamp(): number {
    return this.now().getTime();
  }
}

// Singleton instance
let instance: SimulatedNowProvider | null = null;

export function getSimNowProvider(): SimulatedNowProvider {
  if (!instance) {
    instance = new SimulatedNowProvider();
  }
  return instance;
}

export function resetSimNowProvider(): void {
  if (instance) {
    instance.reset();
  }
}
