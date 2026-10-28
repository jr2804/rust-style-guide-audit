// Fixture for rust-style-guide-audit self-test. Each block violates one rule.
// Expected detections are asserted by scripts/self_test.py.

use std::collections::*;
use std::rc::Rc;
use std::sync::{Arc, Mutex};
use std::collections::{HashMap as Map, hash_map::Entry};

pub struct Pair(pub u32, pub u32);

pub type FrameId = usize;

pub enum Status {
    Ok,
    Fatal,
}

pub struct Config {
    pub retries: u32,
    pub timeout: u32,
}

pub trait StrExt {
    fn shout(&self) -> String;
}

impl StrExt for str {
    fn shout(&self) -> String {
        self.to_uppercase()
    }
}

pub struct Holder {
    data: Vec<u8>,
}

impl Holder {
    pub fn get_data(&self) -> &Vec<u8> {
        &self.data
    }

    pub fn initialize() -> Self {
        Self { data: Vec::new() }
    }

    pub fn parse(input: &String) -> ::std::string::String {
        // long line below intentionally exceeds 100 columns to trigger FMT-01 xxxxxxxxxxxxxxxxxxxxxxxx
        if input.len() > 0 {
            let text = input.parse().unwrap();
            return text;
        }
        if let Some(v) = Some(1u8) {
            if v > 0 {
                let _x = v.unwrap_or(0);
            }
        }
        let map = HashMap::<u32, u32>::new();
        if map.contains_key(&1) {
            let _v = map.get(&1).unwrap();
        }
        assert!(map.is_empty());
        let items = vec![1, 2, 3];
        items.iter().for_each(|i| {
            let _ = i;
        });
        for x in items.iter().map(|v| v * 2).filter(|v| *v > 2) {
            let _ = x;
        }
        let name = "a".to_string() + &"b".to_string();
        let _ = name;
        "".to_string()
    }

    pub fn len(&self) -> usize {
        self.data.len()
    }

    pub fn as_view(&self) -> String {
        String::new()
    }
}

pub fn render(flag: bool) -> u8 {
    if flag { 1 } else { 0 }
}

pub fn dangerous(ptr: *const u8) -> u8 {
    unsafe { *ptr }
}

pub struct Shared {
    inner: Arc<Mutex<Vec<u8>>>,
    other: Rc<u8>,
}

impl Shared {
    pub fn poke(&self) {
        let mut guard = self.inner.lock().unwrap();
        guard.push(1);
        let _ = *self.other;
    }
}

impl From<u8> for Pair {
    fn from(v: u8) -> Self {
        Pair(v as u32, 0)
    }
}

/**
 * Block doc comment.
 */
pub fn documented_block() -> u8 {
    0
}

pub fn panicky(index: usize, items: &[u8]) -> u8 {
    items[index]
}

pub fn manual_default() -> Config {
    Config { retries: 0, timeout: 0 }
}

impl Default for Pair {
    fn default() -> Self {
        Pair(0, 0)
    }
}

pub fn iterate(values: &Vec<u8>) -> u8 {
    let _ = values;
    0
}

pub fn timeouts() -> (u64, u64) {
    // Qualified type paths used twice: the guide wants `use std::time::Duration;`.
    let first = std::time::Duration::from_secs(1);
    let second = std::time::Duration::from_secs(2);
    (first.as_secs(), second.as_secs())
}

pub struct DecodeError {
    message: String,
}

pub fn set_timeout(&mut self, secs: u64) -> u64 {
    let old = self.timeout;
    self.timeout = secs as u32;
    old
}

use std::mem::transmute;

pub fn unqualified_call(ptr: *const u8) -> u8 {
    unsafe { transmute(*ptr) }
}

// A re-export exports the name instead of calling it: IMP-03 is a call-site rule.
pub use std::mem::swap;

pub fn reexport_is_not_a_call(a: &mut u8, b: &mut u8) {
    std::mem::swap(a, b);
}

// A module import is used as a path qualifier, which is what the guide asks for.
use std::mem;

pub fn qualified_call(a: &mut u8, b: &mut u8) {
    mem::swap(a, b);
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn unwrap_is_fine_in_tests() {
        let x: Option<u8> = Some(1);
        assert_eq!(x.unwrap(), 1);
    }
}
