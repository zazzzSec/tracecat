import { Session } from "@supabase/supabase-js"
import { z } from "zod"

import { caseSchema, type Case } from "@/types/schemas"
import { getAuthenticatedClient } from "@/lib/api"

export async function getCases(
  session: Session | null,
  workflowId: string
): Promise<Case[]> {
  try {
    const client = getAuthenticatedClient(session)
    const response = await client.get<Case[]>(`/workflows/${workflowId}/cases`)
    return z.array(caseSchema).parse(response.data)
  } catch (error) {
    console.error("Error fetching cases:", error)
    throw error
  }
}

/**
 * Use this for autocomplete
 *
 * @param session
 * @param workflowId
 * @param cases
 */
export async function updateCases(
  session: Session | null,
  workflowId: string, // They should all have the same workflow ID
  cases: Case[]
) {
  try {
    z.array(caseSchema).parse(cases)
    console.log("Updating cases", cases)
    const client = getAuthenticatedClient(session)
    const responses = await Promise.all(
      cases.map((c) => client.post(`/workflows/${workflowId}/cases/${c.id}`, c))
    )
    if (responses.some((r) => r.status !== 200)) {
      throw new Error("Failed to update cases")
    }
  } catch (error) {
    const err = error as Error
    console.error("Error updating cases:", error)
    console.error("Detail", err.cause, err.message, err.stack)
    throw error
  }
}

export async function fetchCase(
  session: Session | null,
  workflowId: string,
  caseId: string
): Promise<Case> {
  try {
    const client = getAuthenticatedClient(session)
    const response = await client.get<Case>(
      `/workflows/${workflowId}/cases/${caseId}`
    )
    return caseSchema.parse(response.data)
  } catch (error) {
    console.error("Error fetching case:", error)
    throw error
  }
}

export async function updateCase(
  session: Session | null,
  workflowId: string,
  caseId: string,
  case_: Case
) {
  try {
    const client = getAuthenticatedClient(session)
    const response = await client.post(
      `/workflows/${workflowId}/cases/${caseId}`,
      case_
    )
    if (response.status !== 200) {
      throw new Error("Failed to update case")
    }
  } catch (error) {
    console.error("Error updating case:", error)
    throw error
  }
}
