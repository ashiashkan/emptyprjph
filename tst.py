<!-- Toast (top) -->
<div aria-live="polite" aria-atomic="true" class="position-fixed top-0 start-50 translate-middle-x p-3" style="z-index: 1080;">
  <div id="cartToast" class="toast" role="alert" aria-live="assertive" aria-atomic="true" data-bs-delay="8000">
    <div class="toast-header">
      <strong class="me-auto">سبد خرید</strong>
      <small>هم‌اکنون</small>
      <button type="button" class="btn-close" data-bs-dismiss="toast" aria-label="Close"></button>
    </div>
    <div class="toast-body" id="cartToastBody">
      ...
    </div>
  </div>
</div>

<script>
// csrf from cookie
function getCookie(name) {
  let v = null;
  document.cookie.split(';').forEach(c => {
    let [k,val] = c.trim().split('=');
    if (k===name) v = decodeURIComponent(val);
  });
  return v;
}
const csrftoken = getCookie('csrftoken');

document.querySelectorAll('.add-to-cart').forEach(btn => {
  btn.addEventListener('click', async e => {
    const id = btn.dataset.productId;
    const name = btn.dataset.name || '';
    const price = btn.dataset.price || '0';
    const form = new FormData();
    form.append('product_id', id);
    form.append('name', name);
    form.append('price', price);
    form.append('quantity', 1);

    const res = await fetch('{% url "cart_add" %}', {
      method: 'POST',
      headers: {'X-CSRFToken': csrftoken},
      body: form
    });
    const data = await res.json();
    if (data.success) {
      // show toast
      document.getElementById('cartToastBody').textContent = data.message;
      const toastEl = document.getElementById('cartToast');
      const toast = new bootstrap.Toast(toastEl);
      toast.show();
      // update cart count UI if دارید:
      const el = document.querySelector('#cart-count');
      if (el) el.textContent = data.cart_count;
    } else {
      // خطا
      document.getElementById('cartToastBody').textContent = 'خطا، دوباره تلاش کنید';
      new bootstrap.Toast(document.getElementById('cartToast')).show();
    }
  });
});
</script>
