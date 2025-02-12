// market_contract.rs
// This market smart contract provides two functions: create_listing and purchase_listing.
// It calls host functions that are implemented in Python.

extern "C" {
    // Host function for creating a listing.
    // The host (Python) will use pre-passed data.
    fn host_create_listing() -> i32;

    // Host function for purchasing a listing.
    fn host_purchase_listing() -> i32;
}

#[no_mangle]
pub extern "C" fn create_listing() -> i32 {
    unsafe { host_create_listing() }
}

#[no_mangle]
pub extern "C" fn purchase_listing() -> i32 {
    unsafe { host_purchase_listing() }
}