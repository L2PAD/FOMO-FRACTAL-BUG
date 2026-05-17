/**
 * OnChain V2 — ERC20 Indexer Index
 * ==================================
 */

export { ERC20IndexerService, erc20Indexer } from './indexer.service.js';
export { erc20IndexerRoutes } from './routes.js';
export {
  ERC20LogModel,
  SyncStateModel,
  TokenMetadataModel,
  AddressLabelModel,
} from './models.js';

export type {
  IERC20Log,
  ISyncState,
  ITokenMetadata,
  IAddressLabel,
  AddressLabelType,
} from './models.js';

console.log('[OnChain V2] ERC20 Indexer module loaded');
