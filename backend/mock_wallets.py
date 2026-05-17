"""
Mock Wallet Addresses — Real Etherscan addresses for light-mode development.
Used across OTC, Market Makers, Cluster Coverage, Token Intelligence, and Signals.
"""

MOCK_WALLETS = {
    "binance": [
        "0x28C6c06298d514Db089934071355E5743bf21d60",
        "0x21a31Ee1afC51d94C2eFcCAa2092aD1028285549",
        "0xDFd5293D8e347dFe59E90eFd55b2956a1343963d",
    ],
    "coinbase": [
        "0x71660c4005BA85c37ccec55d0C4493E66Fe775d3",
        "0x503828976D22510aad0201ac7EC88293211D23Da",
        "0xA090e606E30bD747d4E6245a1517EbE430F0057e",
    ],
    "okx": [
        "0x6cC5F688a315f3dC28A7781717a9A798a59fDA7b",
        "0x236F233dBf78341d7B04a1fCbA5bfCa703B2153a",
    ],
    "kraken": [
        "0x2910543Af39abA0Cd09dBb2D50200b3E800A63D2",
        "0x267be1C1D684F78cb4F6a176C4911b741E4Ffdc0",
    ],
    "gate.io": [
        "0x0D0707963952f2fBA59dD06f2b425ace40b492Fe",
        "0x1AB4973a48dc892Cd9971ECE8e01DcC7688f8F23",
    ],
    "bybit": [
        "0xf89d7b9c864f589bbF53a82105107622B35EaA40",
        "0x1Db92e2EeBC8E0c075a02BeA49a2935BcD2dFCF4",
    ],
    "generic_whale": [
        "0x8103683202aa8DA10536036EDef04CDd865a225E",
        "0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045",
        "0x47ac0Fb4F2D84898e4D9E7b4DaB3C24507a6D503",
        "0xBE0eB53F46cd790Cd13851d5EFf43D12404d33E8",
    ],
    "market_maker": [
        "0x56Eddb7aa87536c09CCc2793473599fD21A8b17F",
        "0xDbF5E9c5206d0dB70a90108bf936DA60221dC080",
        "0xA7EFAe728D2936e78BDA97dc267687568dD593f3",
        "0xe8c19DB00287e3536075114B2c44c813d52645Cb",
    ],
}


def get_wallets_for_entity(slug: str, limit: int = 3) -> list:
    """Return mock wallet addresses for a given entity slug."""
    key = slug.lower().replace(" ", "").replace("_", "")
    for k, addrs in MOCK_WALLETS.items():
        if k.replace(".", "").replace("_", "").replace(" ", "") in key or key in k.replace(".", "").replace("_", "").replace(" ", ""):
            return addrs[:limit]
    return MOCK_WALLETS["generic_whale"][:limit]


def get_all_wallets_flat(limit: int = 10) -> list:
    """Return a flat list of diverse mock addresses."""
    out = []
    for addrs in MOCK_WALLETS.values():
        out.extend(addrs)
    return out[:limit]
