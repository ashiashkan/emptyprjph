// ...existing code...
def get_exchange_rates():
    """
    Try to fetch rates from CoinGecko (if requests available), otherwise return safe fallbacks.
    Returns mapping like {'BTC': {'USD': Decimal('50000')}, ...}
    """
    try:
        if requests:
            resp = requests.get(
                "https://api.coingecko.com/api/v3/simple/price",
                params={"ids":"bitcoin,ethereum,binancecoin,tron,toncoin,tether","vs_currencies":"usd"},
                timeout=5,
            )
            data = resp.json()
            def _usd(key, fallback):
                return Decimal(str(data.get(key, {}).get('usd', fallback)))
            return {
                'BTC': {'USD': _usd('bitcoin', 50000)},
                'ETH': {'USD': _usd('ethereum', 3000)},
                'BNB': {'USD': _usd('binancecoin', 500)},
                'TRX': {'USD': _usd('tron', 0.12)},
                'TON': {'USD': _usd('toncoin', 2.5)},
                'USDT': {'USD': Decimal('1')},
            }
    except Exception:
        pass

    # fallback static rates
    return {
        'BTC': {'USD': Decimal('50000')},
        'ETH': {'USD': Decimal('3000')},
        'BNB': {'USD': Decimal('500')},
        'TRX': {'USD': Decimal('0.12')},
        'TON': {'USD': Decimal('2.5')},
        'USDT': {'USD': Decimal('1')},
    }
# ...existing code...
def checkout(request):
    if not request.user.is_authenticated:
        messages.error(request, 'برای ادامه خرید باید وارد حساب کاربری خود شوید')
        return redirect('login')

    raw_cart = request.session.get('cart', [])
    # support both dict {id: {...}} and list [{id:..., qty:..., price:...}, ...]
    cart_list = []
    if isinstance(raw_cart, dict):
        for item_id, item_data in raw_cart.items():
            cart_list.append({
                'id': str(item_id),
                'qty': int(item_data.get('qty', 1)),
                'price': float(item_data.get('price', 0)),
            })
    elif isinstance(raw_cart, list):
        # ensure normalized items
        for it in raw_cart:
            cart_list.append({
                'id': str(it.get('id')),
                'qty': int(it.get('qty', 1)),
                'price': float(it.get('price', 0)),
            })

    if not cart_list:
        messages.error(request, 'سبد خرید شما خالی است')
        return redirect('buy_medicine')

    total_amount = sum(it['qty'] * it['price'] for it in cart_list)

    # build cart_items for display by resolving product meta where possible
    cart_items = []
    for it in cart_list:
        product_name = it.get('id')
        # find product in MEDICINES_DATA (best-effort)
        for group in MEDICINES_DATA.get('medicine_groups', {}).values():
            variants = group.get('variants', {}) or {}
            vlist = variants if isinstance(variants, list) else list(variants.values())
            for variant in vlist:
                if str(variant.get('id')) == str(it['id']):
                    product_name = variant.get('name_fa') or variant.get('name_en') or variant.get('name') or product_name
                    break
            if product_name != it.get('id'):
                break

        cart_items.append({
            'id': it['id'],
            'name': product_name,
            'quantity': it['qty'],
            'price': it['price'],
            'total': it['qty'] * it['price'],
        })

    currencies = [
        {'code': 'USDT', 'name': 'Tether (USDT)', 'rate': 1, 'icon': 'fab fa-usd'},
        {'code': 'TRX', 'name': 'TRON (TRX)', 'rate': 0.12, 'icon': 'fab fa-tron'},
        {'code': 'BTC', 'name': 'Bitcoin (BTC)', 'rate': 50000, 'icon': 'fab fa-bitcoin'},
        {'code': 'ETH', 'name': 'Ethereum (ETH)', 'rate': 3000, 'icon': 'fab fa-ethereum'},
        {'code': 'BNB', 'name': 'Binance Coin (BNB)', 'rate': 500, 'icon': 'fab fa-bnb'},
        {'code': 'TON', 'name': 'Toncoin (TON)', 'rate': 2.5, 'icon': 'fas fa-coins'}
    ]

    context = {
        'cart_items': cart_items,
        'total_amount': total_amount,
        'currencies': currencies
    }

    return render(request, 'payment.html', context)
# ...existing code...
def process_payment(request):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'درخواست نامعتبر'})

    try:
        data = json.loads(request.body.decode('utf-8') if isinstance(request.body, bytes) else request.body)
    except Exception:
        data = {}

    currency = data.get('currency')
    address = data.get('address')
    body_amount = data.get('amount')

    # normalize cart (same logic as checkout)
    raw_cart = request.session.get('cart', [])
    cart_list = []
    if isinstance(raw_cart, dict):
        for item_id, item_data in raw_cart.items():
            cart_list.append({
                'id': str(item_id),
                'qty': int(item_data.get('qty', 1)),
                'price': Decimal(str(item_data.get('price', 0)))
            })
    else:
        for it in raw_cart:
            cart_list.append({
                'id': str(it.get('id')),
                'qty': int(it.get('qty', 1)),
                'price': Decimal(str(it.get('price', 0)))
            })

    if not cart_list:
        return JsonResponse({'success': False, 'message': 'سبد خرید خالی است'})

    total_amount = sum(it['qty'] * it['price'] for it in cart_list)
    # If frontend provided an 'amount', ensure it matches or ignore it
    # Create order
    try:
        order = Order.objects.create(
            user=request.user,
            total_amount=total_amount,
            currency=currency or 'USDT',
            crypto_address=address or '',
            status='PENDING'
        )
        for it in cart_list:
            # try resolve product name
            pname = it['id']
            for group in MEDICINES_DATA.get('medicine_groups', {}).values():
                variants = group.get('variants', {}) or {}
                vlist = variants if isinstance(variants, list) else list(variants.values())
                for variant in vlist:
                    if str(variant.get('id')) == str(it['id']):
                        pname = variant.get('name_fa') or variant.get('name_en') or variant.get('name')
                        break
                if pname != it['id']:
                    break

            OrderItem.objects.create(
                order=order,
                product_id=it['id'],
                name=pname,
                price=it['price'],
                quantity=it['qty']
            )

        # clear cart (keep structure of session consistent)
        request.session['cart'] = []
        request.session.modified = True

        return JsonResponse({'success': True, 'order_id': getattr(order, 'order_id', order.id)})
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)})
// ...existing code...