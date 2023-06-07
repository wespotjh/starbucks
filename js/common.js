const searchEL = document.querySelector('.search');
const secrchInputEL = searchEL.querySelector('input');

searchEL.addEventListener('click', function () {
  secrchInputEL.focus()
});

secrchInputEL.addEventListener('focus', function(){
  searchEL.classList.add('focused');
  secrchInputEL.setAttribute('placeholder', '통합검색');
});

secrchInputEL.addEventListener('blur', function(){
  searchEL.classList.remove('focused');
  secrchInputEL.setAttribute('placeholder', '');
});


const thisYear = document.querySelector('.this-year');
thisYear.textContent = new Date().getFullYear(); //2023