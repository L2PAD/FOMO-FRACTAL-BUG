/**
 * OnChain V2 — Bridge Event Decoders
 * ====================================
 * 
 * Decodes bridge events from raw logs.
 * Supports: Optimism, Base (OP Stack), Arbitrum
 */

import { Interface, AbiCoder } from 'ethers';

// ═══════════════════════════════════════════════════════════════
// CONSTANTS
// ═══════════════════════════════════════════════════════════════

// Well-known stablecoin addresses (lowercase)
export const STABLECOIN_ADDRESSES = new Set([
  // ETH Mainnet
  '0xdac17f958d2ee523a2206206994597c13d831ec7', // USDT
  '0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48', // USDC
  '0x6b175474e89094c44da98b954eedeac495271d0f', // DAI
  '0x4fabb145d64652a948d72533023f6e7a623c7c53', // BUSD
  // Arbitrum
  '0xfd086bc7cd5c481dcc9c85ebe478a1c0b69fcbb9', // USDT
  '0xaf88d065e77c8cc2239327c5edb3a432268e5831', // USDC
  '0xff970a61a04b1ca14834a43f5de4533ebddb5cc8', // USDC.e
  '0xda10009cbd5d07dd0cecc66161fc93d7c9000da1', // DAI
  // Optimism
  '0x94b008aa00579c1307b0ef2c499ad98a8ce58e58', // USDT
  '0x0b2c639c533813f4aa9d7837caf62653d097ff85', // USDC
  '0x7f5c764cbc14f9669b88837ca1490cca17c31607', // USDC.e
  '0xda10009cbd5d07dd0cecc66161fc93d7c9000da1', // DAI
  // Base
  '0xd9aaec86b65d86f6a7b5b1b0c42ffa531710b6ca', // USDbC
  '0x833589fcd6edb6e08f4c7c32d4f71b54bda02913', // USDC
]);

// Whale threshold in normalized amount (e.g., 500k tokens)
export const WHALE_THRESHOLD_TOKENS = 500_000;

// ═══════════════════════════════════════════════════════════════
// OP STACK BRIDGE DECODER (Optimism, Base)
// ═══════════════════════════════════════════════════════════════

const OP_BRIDGE_ABI = [
  // L1 → L2 deposits
  'event ETHDepositInitiated(address indexed from, address indexed to, uint256 amount, bytes extraData)',
  'event ERC20DepositInitiated(address indexed l1Token, address indexed l2Token, address indexed from, address to, uint256 amount, bytes extraData)',
  
  // L2 → L1 withdrawals
  'event WithdrawalInitiated(address indexed l1Token, address indexed l2Token, address indexed from, address to, uint256 amount, bytes extraData)',
  'event ETHWithdrawalInitiated(address indexed from, address indexed to, uint256 amount, bytes extraData)',
];

const opBridgeIface = new Interface(OP_BRIDGE_ABI);

// Topic hashes for OP Stack
export const OP_TOPICS = {
  ETH_DEPOSIT: opBridgeIface.getEvent('ETHDepositInitiated')!.topicHash,
  ERC20_DEPOSIT: opBridgeIface.getEvent('ERC20DepositInitiated')!.topicHash,
  ETH_WITHDRAWAL: opBridgeIface.getEvent('ETHWithdrawalInitiated')!.topicHash,
  ERC20_WITHDRAWAL: opBridgeIface.getEvent('WithdrawalInitiated')!.topicHash,
};

// ═══════════════════════════════════════════════════════════════
// ARBITRUM BRIDGE DECODER
// ═══════════════════════════════════════════════════════════════

const ARB_BRIDGE_ABI = [
  // L1 → L2 (Inbox)
  'event MessageDelivered(uint256 indexed messageIndex, bytes32 indexed beforeInboxAcc, address inbox, uint8 kind, address sender, bytes32 messageDataHash, uint256 baseFeeL1, uint64 timestamp)',
  'event InboxMessageDelivered(uint256 indexed messageNum, bytes data)',
  
  // L2 → L1 (Gateway Router)
  'event WithdrawalInitiated(address l1Token, address indexed from, address indexed to, uint256 indexed l2ToL1Id, uint256 exitNum, uint256 amount)',
  'event OutboundTransferInitiated(address indexed token, address indexed from, address indexed to, uint256 amount, bytes data)',
];

const arbBridgeIface = new Interface(ARB_BRIDGE_ABI);

export const ARB_TOPICS = {
  MESSAGE_DELIVERED: arbBridgeIface.getEvent('MessageDelivered')!.topicHash,
  INBOX_MESSAGE: arbBridgeIface.getEvent('InboxMessageDelivered')!.topicHash,
  WITHDRAWAL: arbBridgeIface.getEvent('WithdrawalInitiated')!.topicHash,
  OUTBOUND_TRANSFER: arbBridgeIface.getEvent('OutboundTransferInitiated')!.topicHash,
};

// ═══════════════════════════════════════════════════════════════
// DECODED EVENT TYPE
// ═══════════════════════════════════════════════════════════════

export interface DecodedBridgeEvent {
  eventName: string;
  tokenAddress: string;
  amountRaw: string;
  sender: string;
  receiver?: string;
  isStable: boolean;
  isWhale: boolean;
  rawData?: Record<string, unknown>;
}

// ═══════════════════════════════════════════════════════════════
// DECODER FUNCTIONS
// ═══════════════════════════════════════════════════════════════

/**
 * Decode OP Stack bridge event (Optimism, Base)
 */
export function decodeOpBridgeEvent(log: {
  topics: string[];
  data: string;
  address: string;
}): DecodedBridgeEvent | null {
  const topic0 = log.topics[0]?.toLowerCase();
  
  try {
    // ETH Deposit (L1 → L2)
    if (topic0 === OP_TOPICS.ETH_DEPOSIT.toLowerCase()) {
      const parsed = opBridgeIface.parseLog({ topics: log.topics, data: log.data });
      if (!parsed) return null;
      
      const amount = parsed.args.amount.toString();
      const amountNorm = Number(amount) / 1e18;
      
      return {
        eventName: 'ETHDepositInitiated',
        tokenAddress: '0x0000000000000000000000000000000000000000', // Native ETH
        amountRaw: amount,
        sender: String(parsed.args.from).toLowerCase(),
        receiver: String(parsed.args.to).toLowerCase(),
        isStable: false,
        isWhale: amountNorm >= WHALE_THRESHOLD_TOKENS,
        rawData: { extraData: parsed.args.extraData },
      };
    }
    
    // ERC20 Deposit (L1 → L2)
    if (topic0 === OP_TOPICS.ERC20_DEPOSIT.toLowerCase()) {
      const parsed = opBridgeIface.parseLog({ topics: log.topics, data: log.data });
      if (!parsed) return null;
      
      const tokenAddress = String(parsed.args.l1Token).toLowerCase();
      const amount = parsed.args.amount.toString();
      // Assume 18 decimals for whale check (will be refined with token registry)
      const amountNorm = Number(amount) / 1e18;
      
      return {
        eventName: 'ERC20DepositInitiated',
        tokenAddress,
        amountRaw: amount,
        sender: String(parsed.args.from).toLowerCase(),
        receiver: String(parsed.args.to).toLowerCase(),
        isStable: STABLECOIN_ADDRESSES.has(tokenAddress),
        isWhale: amountNorm >= WHALE_THRESHOLD_TOKENS,
        rawData: { l2Token: parsed.args.l2Token, extraData: parsed.args.extraData },
      };
    }
    
    // ETH Withdrawal (L2 → L1)
    if (topic0 === OP_TOPICS.ETH_WITHDRAWAL.toLowerCase()) {
      const parsed = opBridgeIface.parseLog({ topics: log.topics, data: log.data });
      if (!parsed) return null;
      
      const amount = parsed.args.amount.toString();
      const amountNorm = Number(amount) / 1e18;
      
      return {
        eventName: 'ETHWithdrawalInitiated',
        tokenAddress: '0x0000000000000000000000000000000000000000',
        amountRaw: amount,
        sender: String(parsed.args.from).toLowerCase(),
        receiver: String(parsed.args.to).toLowerCase(),
        isStable: false,
        isWhale: amountNorm >= WHALE_THRESHOLD_TOKENS,
        rawData: { extraData: parsed.args.extraData },
      };
    }
    
    // ERC20 Withdrawal (L2 → L1)
    if (topic0 === OP_TOPICS.ERC20_WITHDRAWAL.toLowerCase()) {
      const parsed = opBridgeIface.parseLog({ topics: log.topics, data: log.data });
      if (!parsed) return null;
      
      const tokenAddress = String(parsed.args.l1Token).toLowerCase();
      const amount = parsed.args.amount.toString();
      const amountNorm = Number(amount) / 1e18;
      
      return {
        eventName: 'WithdrawalInitiated',
        tokenAddress,
        amountRaw: amount,
        sender: String(parsed.args.from).toLowerCase(),
        receiver: String(parsed.args.to).toLowerCase(),
        isStable: STABLECOIN_ADDRESSES.has(tokenAddress),
        isWhale: amountNorm >= WHALE_THRESHOLD_TOKENS,
        rawData: { l2Token: parsed.args.l2Token, extraData: parsed.args.extraData },
      };
    }
  } catch (e) {
    console.warn('[BridgeDecoder] OP decode error:', e);
  }
  
  return null;
}

/**
 * Decode Arbitrum bridge event
 */
export function decodeArbBridgeEvent(log: {
  topics: string[];
  data: string;
  address: string;
}): DecodedBridgeEvent | null {
  const topic0 = log.topics[0]?.toLowerCase();
  
  try {
    // Withdrawal (L2 → L1)
    if (topic0 === ARB_TOPICS.WITHDRAWAL.toLowerCase()) {
      const parsed = arbBridgeIface.parseLog({ topics: log.topics, data: log.data });
      if (!parsed) return null;
      
      const tokenAddress = String(parsed.args.l1Token).toLowerCase();
      const amount = parsed.args.amount.toString();
      const amountNorm = Number(amount) / 1e18;
      
      return {
        eventName: 'WithdrawalInitiated',
        tokenAddress,
        amountRaw: amount,
        sender: String(parsed.args.from).toLowerCase(),
        receiver: String(parsed.args.to).toLowerCase(),
        isStable: STABLECOIN_ADDRESSES.has(tokenAddress),
        isWhale: amountNorm >= WHALE_THRESHOLD_TOKENS,
        rawData: { l2ToL1Id: parsed.args.l2ToL1Id?.toString(), exitNum: parsed.args.exitNum?.toString() },
      };
    }
    
    // Outbound Transfer (L2 → L1)
    if (topic0 === ARB_TOPICS.OUTBOUND_TRANSFER.toLowerCase()) {
      const parsed = arbBridgeIface.parseLog({ topics: log.topics, data: log.data });
      if (!parsed) return null;
      
      const tokenAddress = String(parsed.args.token).toLowerCase();
      const amount = parsed.args.amount.toString();
      const amountNorm = Number(amount) / 1e18;
      
      return {
        eventName: 'OutboundTransferInitiated',
        tokenAddress,
        amountRaw: amount,
        sender: String(parsed.args.from).toLowerCase(),
        receiver: String(parsed.args.to).toLowerCase(),
        isStable: STABLECOIN_ADDRESSES.has(tokenAddress),
        isWhale: amountNorm >= WHALE_THRESHOLD_TOKENS,
      };
    }
    
    // Message Delivered (L1 → L2) - complex, simplified handling
    if (topic0 === ARB_TOPICS.MESSAGE_DELIVERED.toLowerCase()) {
      // This event is complex and requires additional decoding
      // For now, we'll capture it but mark as unknown token
      return {
        eventName: 'MessageDelivered',
        tokenAddress: '0x0000000000000000000000000000000000000000',
        amountRaw: '0',
        sender: log.address.toLowerCase(),
        isStable: false,
        isWhale: false,
        rawData: { note: 'Complex event, requires additional decoding' },
      };
    }
  } catch (e) {
    console.warn('[BridgeDecoder] ARB decode error:', e);
  }
  
  return null;
}

/**
 * Get all topic hashes for a bridge family
 */
export function getBridgeTopics(bridge: 'OPTIMISM' | 'BASE' | 'ARBITRUM'): string[] {
  if (bridge === 'OPTIMISM' || bridge === 'BASE') {
    return Object.values(OP_TOPICS);
  }
  if (bridge === 'ARBITRUM') {
    return Object.values(ARB_TOPICS);
  }
  return [];
}

/**
 * Check if a token is a stablecoin
 */
export function isStablecoin(tokenAddress: string): boolean {
  return STABLECOIN_ADDRESSES.has(tokenAddress.toLowerCase());
}

console.log('[OnChain V2] Bridge Decoders loaded');
