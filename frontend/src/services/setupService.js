/**
 * Setup Service
 * ==============
 * API client for Setup Engine endpoints.
 */

const API_URL = process.env.REACT_APP_BACKEND_URL || '';

class SetupService {
  /**
   * Get full setup analysis
   */
  async getSetup(symbol, timeframe = '1D') {
    try {
      const tf = timeframe.toUpperCase();
      const response = await fetch(`${API_URL}/api/ta/setup?symbol=${symbol}&tf=${tf}`);
      if (!response.ok) throw new Error('Failed to fetch setup');
      return await response.json();
    } catch (error) {
      console.error('SetupService.getSetup error:', error);
      throw error;
    }
  }

  /**
   * Get setup with Structure-First architecture (v2)
   * Returns structure_context, primary_pattern, alternative_patterns
   */
  async getSetupV2(symbol, timeframe = '1D') {
    try {
      const tf = timeframe.toUpperCase();
      const response = await fetch(`${API_URL}/api/ta/setup/v2?symbol=${symbol}&tf=${tf}`);
      if (!response.ok) throw new Error('Failed to fetch setup v2');
      return await response.json();
    } catch (error) {
      console.error('SetupService.getSetupV2 error:', error);
      throw error;
    }
  }

  /**
   * Get confluence analysis
   */
  async getConfluence(symbol, timeframe = '1d') {
    try {
      const response = await fetch(`${API_URL}/api/ta/confluence/${symbol}/${timeframe}`);
      if (!response.ok) throw new Error('Failed to fetch confluence');
      return await response.json();
    } catch (error) {
      console.error('SetupService.getConfluence error:', error);
      throw error;
    }
  }

  /**
   * Get detected patterns
   */
  async getPatterns(symbol, timeframe = '1d') {
    try {
      const response = await fetch(`${API_URL}/api/ta/patterns/${symbol}/${timeframe}`);
      if (!response.ok) throw new Error('Failed to fetch patterns');
      return await response.json();
    } catch (error) {
      console.error('SetupService.getPatterns error:', error);
      throw error;
    }
  }

  /**
   * Get key levels
   */
  async getLevels(symbol, timeframe = '1d') {
    try {
      const response = await fetch(`${API_URL}/api/ta/levels/${symbol}/${timeframe}`);
      if (!response.ok) throw new Error('Failed to fetch levels');
      return await response.json();
    } catch (error) {
      console.error('SetupService.getLevels error:', error);
      throw error;
    }
  }

  /**
   * Get market structure
   */
  async getStructure(symbol, timeframe = '1d') {
    try {
      const response = await fetch(`${API_URL}/api/ta/structure/${symbol}/${timeframe}`);
      if (!response.ok) throw new Error('Failed to fetch structure');
      return await response.json();
    } catch (error) {
      console.error('SetupService.getStructure error:', error);
      throw error;
    }
  }

  /**
   * Get indicator signals
   */
  async getIndicators(symbol, timeframe = '1d') {
    try {
      const response = await fetch(`${API_URL}/api/ta/indicators/${symbol}/${timeframe}`);
      if (!response.ok) throw new Error('Failed to fetch indicators');
      return await response.json();
    } catch (error) {
      console.error('SetupService.getIndicators error:', error);
      throw error;
    }
  }

  // ============================================
  // IDEAS API
  // ============================================

  /**
   * Create new idea with snapshot
   * @param {string} asset - Symbol (e.g., BTC, ETH)
   * @param {string} timeframe - Timeframe (e.g., 1D, 4H)
   * @param {Array} tags - Optional tags
   * @param {string} notes - Optional notes
   * @param {Object} snapshot - Current TA snapshot to save
   */
  async createIdea(asset, timeframe, tags = [], notes = '', snapshot = null) {
    try {
      const response = await fetch(`${API_URL}/api/ta/ideas`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ asset, timeframe, tags, notes, snapshot }),
      });
      if (!response.ok) throw new Error('Failed to create idea');
      return await response.json();
    } catch (error) {
      console.error('SetupService.createIdea error:', error);
      throw error;
    }
  }

  /**
   * List ideas
   */
  async listIdeas(filters = {}) {
    try {
      const params = new URLSearchParams();
      if (filters.asset) params.append('asset', filters.asset);
      if (filters.status) params.append('status', filters.status);
      if (filters.limit) params.append('limit', filters.limit);
      
      const url = `${API_URL}/api/ta/ideas${params.toString() ? '?' + params.toString() : ''}`;
      const response = await fetch(url);
      if (!response.ok) throw new Error('Failed to list ideas');
      return await response.json();
    } catch (error) {
      console.error('SetupService.listIdeas error:', error);
      throw error;
    }
  }

  /**
   * Get idea by ID
   */
  async getIdea(ideaId) {
    try {
      const response = await fetch(`${API_URL}/api/ta/ideas/${ideaId}`);
      if (!response.ok) throw new Error('Failed to fetch idea');
      return await response.json();
    } catch (error) {
      console.error('SetupService.getIdea error:', error);
      throw error;
    }
  }

  /**
   * Update idea (create new version)
   */
  async updateIdea(ideaId) {
    try {
      const response = await fetch(`${API_URL}/api/ta/ideas/${ideaId}/update`, {
        method: 'POST',
      });
      if (!response.ok) throw new Error('Failed to update idea');
      return await response.json();
    } catch (error) {
      console.error('SetupService.updateIdea error:', error);
      throw error;
    }
  }

  /**
   * Update idea (create new version)
   */
  async updateIdea(ideaId) {
    try {
      const response = await fetch(`${API_URL}/api/ta/ideas/${ideaId}/update`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
      });
      if (!response.ok) throw new Error('Failed to update idea');
      return await response.json();
    } catch (error) {
      console.error('SetupService.updateIdea error:', error);
      throw error;
    }
  }

  /**
   * Validate idea
   */
  async validateIdea(ideaId, currentPrice = null) {
    try {
      const response = await fetch(`${API_URL}/api/ta/ideas/${ideaId}/validate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ current_price: currentPrice }),
      });
      if (!response.ok) throw new Error('Failed to validate idea');
      return await response.json();
    } catch (error) {
      console.error('SetupService.validateIdea error:', error);
      throw error;
    }
  }

  /**
   * Get idea timeline
   */
  async getIdeaTimeline(ideaId) {
    try {
      const response = await fetch(`${API_URL}/api/ta/ideas/${ideaId}/timeline`);
      if (!response.ok) throw new Error('Failed to fetch timeline');
      return await response.json();
    } catch (error) {
      console.error('SetupService.getIdeaTimeline error:', error);
      throw error;
    }
  }

  /**
   * Delete idea
   */
  async deleteIdea(ideaId) {
    try {
      const response = await fetch(`${API_URL}/api/ta/ideas/${ideaId}`, {
        method: 'DELETE',
      });
      if (!response.ok) throw new Error('Failed to delete idea');
      return await response.json();
    } catch (error) {
      console.error('SetupService.deleteIdea error:', error);
      throw error;
    }
  }
}

// Singleton
const setupService = new SetupService();
export default setupService;
