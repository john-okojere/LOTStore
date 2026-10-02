const close = document.getElementById('close_nav_menu');
const open = document.getElementById('open_nav_menu');
const menu = document.getElementById('nav_menu');
const list = document.getElementById('sidebar');
const body = document.getElementById('body');

// close.addEventListener('click', ()=> {
//     menu.classList.remove('activatemenu');
//     menu.style.display ="none"
// } )
// open.addEventListener('click', ()=> {
//     menu.style.display ="block"
//     menu.classList.add('activatemenu')

// } )

const icon = document.getElementById('list_icon');
const icon_close = document.getElementById('list_icon_close');
// const opc = document.getElementById('option_icon');
const box = document.getElementById('main_box');

icon_close.style.display= "none";
function iconopen(){
    list.style.width = "60vw";
    // opc.style.left = "60vw";
    box.style.width = '40vw';
    box.style.opacity = 0;
    icon.style.display = "none";
    icon_close.style.display= "block";
}
function iconclose(){
    list.style.width = "0";
    // opc.style.left = "0";
    box.style.opacity = 1;
    box.style.width = '100vw'
    icon.style.display = "block";
    icon_close.style.display= "none";
}

function openimgmodal() {
    document.getElementById('modal-img').style.display="flex";  
}
function closeimgmodal() {
    document.getElementById('modal-img').style.display="none";  
}
function profilemodal(n){
    var modal = document.getElementById('profile-modal-'+ n );
    modal.style.display="flex";
    console.log(modal)
}

function closeprofilemodal(n){
    var modal = document.getElementById('profile-modal-'+ n );
    modal.style.display="none";
    console.log(modal)
    
}