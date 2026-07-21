//! Pure GHOST fork-choice + LMD weight aggregation (byte-aligned with consensus/ghost.py).

use pyo3::prelude::*;
use serde_json::{Map, Value};
use std::collections::{HashMap, HashSet};

const MAX_GHOST_NODES: usize = 100_000;
const MAX_LMD_VALIDATORS: usize = 50_000;

#[derive(Clone, Default)]
struct Node {
    parent: Option<String>,
    number: i64,
    children: Vec<String>,
}

fn parse_tree(tree_json: &str) -> PyResult<HashMap<String, Node>> {
    let value: Value = serde_json::from_str(tree_json)
        .map_err(|e| pyo3::exceptions::PyValueError::new_err(e.to_string()))?;
    let obj = value
        .as_object()
        .ok_or_else(|| pyo3::exceptions::PyValueError::new_err("tree_json must be object"))?;
    if obj.len() > MAX_GHOST_NODES {
        return Err(pyo3::exceptions::PyValueError::new_err(format!(
            "too_many_ghost_nodes: {} > {}",
            obj.len(),
            MAX_GHOST_NODES
        )));
    }
    let mut tree = HashMap::with_capacity(obj.len());
    for (hash, data) in obj {
        let row = data.as_object().ok_or_else(|| {
            pyo3::exceptions::PyValueError::new_err("tree node must be object")
        })?;
        let parent = row
            .get("parent")
            .and_then(|v| {
                if v.is_null() {
                    None
                } else {
                    v.as_str().map(|s| s.to_string())
                }
            });
        let number = row
            .get("number")
            .and_then(|v| v.as_i64().or_else(|| v.as_u64().map(|u| u as i64)))
            .unwrap_or(0);
        let children = row
            .get("children")
            .and_then(|v| v.as_array())
            .map(|arr| {
                arr.iter()
                    .filter_map(|c| c.as_str().map(|s| s.to_string()))
                    .collect::<Vec<_>>()
            })
            .unwrap_or_default();
        tree.insert(
            hash.clone(),
            Node {
                parent,
                number,
                children,
            },
        );
    }
    Ok(tree)
}

fn parse_weights(weights_json: &str) -> PyResult<HashMap<String, i64>> {
    let value: Value = serde_json::from_str(weights_json)
        .map_err(|e| pyo3::exceptions::PyValueError::new_err(e.to_string()))?;
    let obj = value
        .as_object()
        .ok_or_else(|| pyo3::exceptions::PyValueError::new_err("weights_json must be object"))?;
    if obj.len() > MAX_GHOST_NODES {
        return Err(pyo3::exceptions::PyValueError::new_err(format!(
            "too_many_weight_entries: {} > {}",
            obj.len(),
            MAX_GHOST_NODES
        )));
    }
    let mut weights = HashMap::with_capacity(obj.len());
    for (hash, v) in obj {
        let w = v
            .as_i64()
            .or_else(|| v.as_u64().map(|u| u as i64))
            .or_else(|| v.as_f64().map(|f| f as i64))
            .unwrap_or(0);
        weights.insert(hash.clone(), w);
    }
    Ok(weights)
}

fn cumulative_weight_inner(
    block_hash: &str,
    tree: &HashMap<String, Node>,
    weights: &HashMap<String, i64>,
) -> i64 {
    let mut memo: HashMap<String, i64> = HashMap::new();
    let mut stack: Vec<(String, bool)> = vec![(block_hash.to_string(), false)];

    while let Some((node, expanded)) = stack.pop() {
        if expanded {
            let mut total = *weights.get(&node).unwrap_or(&0);
            if let Some(entry) = tree.get(&node) {
                for child in &entry.children {
                    total += *memo.get(child).unwrap_or(&0);
                }
            }
            memo.insert(node, total);
        } else {
            stack.push((node.clone(), true));
            if let Some(entry) = tree.get(&node) {
                for child in entry.children.iter().rev() {
                    if !memo.contains_key(child) {
                        stack.push((child.clone(), false));
                    }
                }
            }
        }
    }

    *memo
        .get(block_hash)
        .unwrap_or_else(|| weights.get(block_hash).unwrap_or(&0))
}

fn select_head_inner(
    tree: &HashMap<String, Node>,
    weights: &HashMap<String, i64>,
) -> Option<String> {
    if tree.is_empty() {
        return None;
    }

    let mut genesis: Option<String> = None;
    for (hash, data) in tree {
        if data.parent.is_none() {
            genesis = Some(hash.clone());
            break;
        }
    }
    let mut current = genesis?;
    let mut visited: HashSet<String> = HashSet::new();

    while !visited.contains(&current) {
        visited.insert(current.clone());
        let children = tree
            .get(&current)
            .map(|n| n.children.clone())
            .unwrap_or_default();
        if children.is_empty() {
            return Some(current);
        }

        let mut best_child: Option<String> = None;
        let mut best_weight: i64 = -1;

        for child in &children {
            let cum = cumulative_weight_inner(child, tree, weights);
            if cum > best_weight {
                best_weight = cum;
                best_child = Some(child.clone());
            } else if cum == best_weight {
                if let Some(ref best) = best_child {
                    let child_num = tree.get(child).map(|n| n.number).unwrap_or(0);
                    let best_num = tree.get(best).map(|n| n.number).unwrap_or(0);
                    if child_num > best_num {
                        best_child = Some(child.clone());
                    } else if child_num == best_num && child < best {
                        best_child = Some(child.clone());
                    }
                } else {
                    best_child = Some(child.clone());
                }
            }
        }

        match best_child {
            Some(next) => current = next,
            None => return Some(current),
        }
    }
    Some(current)
}

fn chain_from_head_inner(
    tree: &HashMap<String, Node>,
    weights: &HashMap<String, i64>,
) -> Vec<String> {
    let Some(head) = select_head_inner(tree, weights) else {
        return Vec::new();
    };
    let mut chain = Vec::new();
    let mut current = Some(head);
    while let Some(hash) = current {
        chain.push(hash.clone());
        current = tree.get(&hash).and_then(|n| n.parent.clone());
    }
    chain.reverse();
    chain
}

#[pyfunction]
fn ghost_cumulative_weight(
    block_hash: String,
    tree_json: String,
    weights_json: String,
) -> PyResult<i64> {
    let tree = parse_tree(&tree_json)?;
    let weights = parse_weights(&weights_json)?;
    Ok(cumulative_weight_inner(&block_hash, &tree, &weights))
}

#[pyfunction]
fn ghost_select_head(tree_json: String, weights_json: String) -> PyResult<Option<String>> {
    let tree = parse_tree(&tree_json)?;
    let weights = parse_weights(&weights_json)?;
    Ok(select_head_inner(&tree, &weights))
}

#[pyfunction]
fn ghost_chain_from_head(tree_json: String, weights_json: String) -> PyResult<Vec<String>> {
    let tree = parse_tree(&tree_json)?;
    let weights = parse_weights(&weights_json)?;
    Ok(chain_from_head_inner(&tree, &weights))
}

/// Aggregate LMD latest votes into block weights: {block_hash: stake_sum}.
#[pyfunction]
fn lmd_compute_weights(votes_json: String, stakes_json: String) -> PyResult<String> {
    let votes: Value = serde_json::from_str(&votes_json)
        .map_err(|e| pyo3::exceptions::PyValueError::new_err(e.to_string()))?;
    let stakes: Value = serde_json::from_str(&stakes_json)
        .map_err(|e| pyo3::exceptions::PyValueError::new_err(e.to_string()))?;
    let votes = votes
        .as_object()
        .ok_or_else(|| pyo3::exceptions::PyValueError::new_err("votes_json must be object"))?;
    let stakes = stakes
        .as_object()
        .ok_or_else(|| pyo3::exceptions::PyValueError::new_err("stakes_json must be object"))?;
    if votes.len() > MAX_LMD_VALIDATORS || stakes.len() > MAX_LMD_VALIDATORS {
        return Err(pyo3::exceptions::PyValueError::new_err(
            "too_many_lmd_validators",
        ));
    }

    let mut weights: Map<String, Value> = Map::new();
    for (validator, vote) in votes {
        let block_hash = if let Some(arr) = vote.as_array() {
            arr.first()
                .and_then(|v| v.as_str())
                .unwrap_or("")
                .to_string()
        } else if let Some(obj) = vote.as_object() {
            obj.get("block_hash")
                .or_else(|| obj.get("0"))
                .and_then(|v| v.as_str())
                .unwrap_or("")
                .to_string()
        } else {
            String::new()
        };
        if block_hash.is_empty() {
            continue;
        }
        let stake = stakes
            .get(validator)
            .and_then(|v| v.as_i64().or_else(|| v.as_u64().map(|u| u as i64)))
            .unwrap_or(0);
        let entry = weights.entry(block_hash).or_insert(Value::Number(0.into()));
        let cur = entry.as_i64().unwrap_or(0);
        *entry = Value::Number((cur + stake).into());
    }
    serde_json::to_string(&Value::Object(weights))
        .map_err(|e| pyo3::exceptions::PyValueError::new_err(e.to_string()))
}

pub fn register(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(ghost_cumulative_weight, m)?)?;
    m.add_function(wrap_pyfunction!(ghost_select_head, m)?)?;
    m.add_function(wrap_pyfunction!(ghost_chain_from_head, m)?)?;
    m.add_function(wrap_pyfunction!(lmd_compute_weights, m)?)?;
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn linear_chain_head() {
        let mut tree_map = Map::new();
        let mut weights_map = Map::new();
        let mut prev: Option<String> = None;
        for i in 0..20 {
            let h = format!("block_{i:04}");
            let mut node = Map::new();
            match &prev {
                Some(p) => node.insert("parent".into(), Value::String(p.clone())),
                None => node.insert("parent".into(), Value::Null),
            }
            node.insert("number".into(), Value::Number(i.into()));
            node.insert("children".into(), Value::Array(vec![]));
            if let Some(p) = &prev {
                if let Some(Value::Object(parent)) = tree_map.get_mut(p) {
                    if let Some(Value::Array(children)) = parent.get_mut("children") {
                        children.push(Value::String(h.clone()));
                    }
                }
            }
            tree_map.insert(h.clone(), Value::Object(node));
            weights_map.insert(h.clone(), Value::Number(1.into()));
            prev = Some(h);
        }
        let tree = serde_json::to_string(&Value::Object(tree_map)).unwrap();
        let weights = serde_json::to_string(&Value::Object(weights_map)).unwrap();
        assert_eq!(
            ghost_select_head(tree.clone(), weights.clone())
                .unwrap()
                .as_deref(),
            Some("block_0019")
        );
        assert_eq!(
            ghost_cumulative_weight("block_0000".into(), tree, weights).unwrap(),
            20
        );
    }
}
