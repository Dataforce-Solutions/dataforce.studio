import type { JournalTransaction } from './types'

export interface CatchUpGroup {
  actor: string
  intent: string
  transactions: JournalTransaction[]
}

export const groupTransactionsByIntent = (transactions: JournalTransaction[]): CatchUpGroup[] => {
  const groups = new Map<string, CatchUpGroup>()
  for (const transaction of transactions) {
    const key = JSON.stringify([transaction.actor, transaction.intent])
    const group = groups.get(key)
    if (group) group.transactions.push(transaction)
    else {
      groups.set(key, {
        actor: transaction.actor,
        intent: transaction.intent,
        transactions: [transaction],
      })
    }
  }
  return [...groups.values()]
}
