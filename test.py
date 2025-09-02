# ... کدهای قبلی ...

class CartView(View):
    def get(self, request):
        lang = request.session.get('language', 'fa')
        cart = request.session.get('cart', [])
        total = sum(float(i.get('price',0))*int(i.get('qty',1)) for i in cart)
        return render(request, 'cart.html', {'cart': cart, 'total': total, 'lang': lang})

    def post(self, request):
        action = request.POST.get('action')
        cart = request.session.get('cart', [])
        
        if action == 'remove':
            idx = int(request.POST.get('index', -1))
            if 0 <= idx < len(cart):
                del cart[idx]
                messages.success(request, "محصول از سبد خرید حذف شد.")
                
        elif action == 'update':
            idx = int(request.POST.get('index', -1))
            qty = int(request.POST.get('qty', 1))
            if 0 <= idx < len(cart) and qty > 0:
                cart[idx]['qty'] = qty
                messages.success(request, "تعداد محصول به‌روزرسانی شد.")
                
        elif action == 'checkout':
            if not request.user.is_authenticated:
                messages.warning(request, 'ابتدا وارد شوید')
                return redirect('login')
            if not getattr(request.user, 'address', None):
                messages.warning(request, get_text(request.session.get('language','fa'), 'register_first'))
                return redirect('profile')
            return redirect('payment')
            
        request.session['cart'] = cart
        request.session.modified = True
        return redirect('cart')

# ... بقیه کدها ...