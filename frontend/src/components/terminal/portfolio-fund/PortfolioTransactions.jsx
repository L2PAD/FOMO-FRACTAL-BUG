export default function PortfolioTransactions() {
  const mockTransactions = [
    {
      date: 'Apr 17, 2025',
      asset: 'BTC',
      type: 'Buy',
      qty: 0.05,
      price: 64000,
      total: 3200,
      fee: 12,
      status: 'Completed'
    },
    {
      date: 'Apr 15, 2025',
      asset: 'ETH',
      type: 'Sell',
      qty: 0.2,
      price: 3500,
      total: 700,
      fee: 2.8,
      status: 'Completed'
    },
    {
      date: 'Apr 12, 2025',
      asset: 'SOL',
      type: 'Buy',
      qty: 38.2,
      price: 142,
      total: 5424,
      fee: 18,
      status: 'Completed'
    }
  ];

  return (
    <div className="bg-white border border-[#E5E7EB] rounded-lg p-3" data-testid="transactions">
      <div className="mb-3">
        <h3 className="text-sm font-semibold text-gray-900">Transactions</h3>
        <p className="text-xs text-gray-500">Latest capital movements</p>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full text-xs">
          <thead>
            <tr className="border-b border-[#E5E7EB]">
              <th className="text-left py-1.5 px-2 text-xs font-semibold text-gray-500 uppercase">Date</th>
              <th className="text-left py-1.5 px-2 text-xs font-semibold text-gray-500 uppercase">Asset</th>
              <th className="text-left py-1.5 px-2 text-xs font-semibold text-gray-500 uppercase">Type</th>
              <th className="text-right py-1.5 px-2 text-xs font-semibold text-gray-500 uppercase">Qty</th>
              <th className="text-right py-1.5 px-2 text-xs font-semibold text-gray-500 uppercase">Price</th>
              <th className="text-right py-1.5 px-2 text-xs font-semibold text-gray-500 uppercase">Total</th>
              <th className="text-right py-1.5 px-2 text-xs font-semibold text-gray-500 uppercase">Fee</th>
              <th className="text-center py-1.5 px-2 text-xs font-semibold text-gray-500 uppercase">Status</th>
            </tr>
          </thead>
          <tbody>
            {mockTransactions.map((tx, i) => (
              <tr key={i} className="border-b border-gray-100 hover:bg-gray-50">
                <td className="py-2 px-2 text-gray-700">{tx.date}</td>
                <td className="py-2 px-2 font-semibold text-gray-900">{tx.asset}</td>
                <td className="py-2 px-2">
                  <span className={`px-1.5 py-0.5 text-xs font-medium rounded ${
                    tx.type === 'Buy' ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'
                  }`}>
                    {tx.type}
                  </span>
                </td>
                <td className="py-2 px-2 text-right font-mono text-gray-900">{tx.qty}</td>
                <td className="py-2 px-2 text-right font-mono text-gray-900">${tx.price.toLocaleString()}</td>
                <td className="py-2 px-2 text-right font-mono font-semibold text-gray-900">${tx.total.toLocaleString()}</td>
                <td className="py-2 px-2 text-right font-mono text-gray-600">${tx.fee}</td>
                <td className="py-2 px-2 text-center">
                  <span className="px-1.5 py-0.5 text-xs font-medium rounded-lg bg-green-100 text-green-700">
                    {tx.status}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
