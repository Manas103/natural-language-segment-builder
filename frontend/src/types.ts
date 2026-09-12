// Mirrors segment_builder/schema.py. Kept in sync by hand; a change to the
// Python schema that is not reflected here is a known limitation (see README).

export type EventOperator = "count_gte" | "count_gt" | "count_lte" | "count_lt" | "count_eq";
export type AttributeOperator = "eq" | "neq" | "gt" | "gte" | "lt" | "lte" | "in" | "contains";

export interface EventPredicate {
  type: "event";
  event_name: string;
  operator: EventOperator;
  count: number;
  within_days?: number;
}

export interface AttributePredicate {
  type: "attribute";
  field: string;
  operator: AttributeOperator;
  value: string | number | boolean | string[];
}

export interface Composite {
  type: "and" | "or" | "not";
  children: PredicateNode[];
}

export type PredicateNode = EventPredicate | AttributePredicate | Composite;

export interface SegmentDefinition {
  version: "1.0";
  root: PredicateNode;
}

export interface SegmentPreviewResponse {
  requestText: string;
  definition: SegmentDefinition;
  liveCount: number;
}
