from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.contrib import messages
from django.utils import timezone
from django.db import transaction
from django.db.models import Sum, F, DecimalField, Count, Max
from django.db.models.functions import TruncDate
from django.core.paginator import Paginator
from datetime import timedelta

from .models import Product, Order, OrderItem
from .forms import ProductForm, StockUpdateForm

# Create your views here.


def _get_cart(request):
    return request.session.get('cart', {})


def _save_cart(request, cart):
    request.session['cart'] = cart
    request.session.modified = True


def home(request):
    return render(request, 'home.html')

def login_view(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        
        user = authenticate(request, username=username, password=password)
        
        if user is not None:
            login(request, user)
            
            # Check if user is admin (superuser or staff)
            if user.is_superuser or user.is_staff:
                return redirect('admin_dashboard')
            else:
                return redirect('customer_dashboard')
        else:
            messages.error(request, 'Invalid username or password.')
    
    return render(request, 'login.html')

def logout_view(request):
    logout(request)
    messages.success(request, 'You have been logged out successfully.')
    return redirect('login')

def register_view(request):
    if request.method == 'POST':
        first_name = request.POST.get('first_name')
        last_name = request.POST.get('last_name')
        username = request.POST.get('username')
        email = request.POST.get('email')
        password = request.POST.get('password')
        confirm_password = request.POST.get('confirm_password')
        
        if password == confirm_password:
            if User.objects.filter(username=username).exists():
                messages.error(request, 'Username already exists.')
            elif User.objects.filter(email=email).exists():
                messages.error(request, 'Email already exists.')
            else:
                user = User.objects.create_user(
                    username=username,
                    email=email,
                    password=password,
                    first_name=first_name,
                    last_name=last_name
                )
                messages.success(request, 'Account created successfully! Please login.')
                return redirect('login')
        else:
            messages.error(request, 'Passwords do not match.')
    
    return render(request, 'register.html')

def customer_dashboard(request):
    if not request.user.is_authenticated:
        return redirect('login')
    
    if request.user.is_superuser or request.user.is_staff:
        return redirect('admin_dashboard')
    
    # Customer-specific stats
    customer = request.user
    orders_qs = Order.objects.filter(customer=customer)

    total_orders = orders_qs.count()
    pending_deliveries = orders_qs.filter(
        status__in=[
            Order.STATUS_PENDING,
            Order.STATUS_PREPARING,
            Order.STATUS_OUT_FOR_DELIVERY,
        ]
    ).count()
    completed_orders = orders_qs.filter(status=Order.STATUS_COMPLETED).count()

    # Total spent = items total + delivery fees for completed orders
    items_spent_agg = OrderItem.objects.filter(
        order__customer=customer,
        order__status=Order.STATUS_COMPLETED,
    ).aggregate(
        total=Sum(
            F('quantity') * F('price'),
            output_field=DecimalField(max_digits=12, decimal_places=2),
        )
    )
    items_total = items_spent_agg['total'] or 0

    delivery_spent_agg = Order.objects.filter(
        customer=customer,
        status=Order.STATUS_COMPLETED,
    ).aggregate(
        total_fee=Sum(
            F('delivery_fee'),
            output_field=DecimalField(max_digits=12, decimal_places=2),
        )
    )
    delivery_total = delivery_spent_agg['total_fee'] or 0

    total_spent = items_total + delivery_total

    context = {
        'total_orders': total_orders,
        'pending_deliveries': pending_deliveries,
        'completed_orders': completed_orders,
        'total_spent': total_spent,
    }

    return render(request, 'customer_dashboard.html', context)


def customer_orders(request):
    if not request.user.is_authenticated:
        return redirect('login')

    if request.user.is_superuser or request.user.is_staff:
        return redirect('admin_dashboard')

    customer = request.user

    base_orders = (
        Order.objects.filter(customer=customer)
        .annotate(
            items_count=Count('items', distinct=True),
            total_amount=Sum(
                F('items__quantity') * F('items__price'),
                output_field=DecimalField(max_digits=12, decimal_places=2),
            ),
        )
        .order_by('-created_at')
    )

    status_filter = request.GET.get('status', 'all')

    orders = base_orders
    if status_filter != 'all':
        orders = orders.filter(status=status_filter)

    active_orders = base_orders.filter(
        status__in=[
            Order.STATUS_PENDING,
            Order.STATUS_PREPARING,
            Order.STATUS_OUT_FOR_DELIVERY,
        ]
    )

    context = {
        'orders': orders,
        'active_orders': active_orders,
        'status_filter': status_filter,
    }

    return render(request, 'customer_orders.html', context)


def shop_now(request):
    if not request.user.is_authenticated:
        return redirect('login')

    if request.user.is_superuser or request.user.is_staff:
        return redirect('admin_dashboard')

    query = request.GET.get('q', '').strip()
    category_filter = request.GET.get('category', 'all')

    products = Product.objects.filter(is_active=True, stock_quantity__gt=0).order_by('category', 'name')

    if query:
        products = products.filter(name__icontains=query)

    if category_filter == 'fruits':
        products = products.filter(category__iexact='Fruits')
    elif category_filter == 'vegetables':
        products = products.filter(category__iexact='Vegetables')

    paginator = Paginator(products, 9)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'products': page_obj,
        'page_obj': page_obj,
        'paginator': paginator,
        'query': query,
        'category_filter': category_filter,
    }

    return render(request, 'shop_now.html', context)


def cart_view(request):
    if not request.user.is_authenticated:
        return redirect('login')

    if request.user.is_superuser or request.user.is_staff:
        return redirect('admin_dashboard')

    cart = _get_cart(request)
    product_ids = [int(pid) for pid in cart.keys()]

    cart_items = []
    cart_total = 0.0
    cart_total_items = 0.0

    if product_ids:
        products = Product.objects.filter(id__in=product_ids, is_active=True)
        products_map = {p.id: p for p in products}

        for pid_str, quantity in cart.items():
            try:
                pid = int(pid_str)
                qty = float(quantity)
            except (ValueError, TypeError):
                continue

            product = products_map.get(pid)
            if not product:
                continue

            subtotal = qty * float(product.price)
            cart_items.append(
                {
                    'product': product,
                    'quantity': qty,
                    'subtotal': subtotal,
                }
            )
            cart_total += subtotal
            cart_total_items += qty

    context = {
        'cart_items': cart_items,
        'cart_total': cart_total,
        'cart_total_items': cart_total_items,
    }

    return render(request, 'add_to_cart.html', context)


def checkout_view(request):
    if not request.user.is_authenticated:
        return redirect('login')

    if request.user.is_superuser or request.user.is_staff:
        return redirect('admin_dashboard')

    cart = _get_cart(request)

    if not cart:
        messages.warning(request, 'Your cart is empty.')
        return redirect('cart_view')

    product_ids = [int(pid) for pid in cart.keys()]

    cart_items = []
    cart_total = 0.0
    cart_total_items = 0.0

    if product_ids:
        products = Product.objects.filter(id__in=product_ids, is_active=True)
        products_map = {p.id: p for p in products}

        for pid_str, quantity in cart.items():
            try:
                pid = int(pid_str)
                qty = float(quantity)
            except (ValueError, TypeError):
                continue

            product = products_map.get(pid)
            if not product:
                continue

            subtotal = qty * float(product.price)
            cart_items.append(
                {
                    'product': product,
                    'quantity': qty,
                    'subtotal': subtotal,
                }
            )
            cart_total += subtotal
            cart_total_items += qty

    delivery_method = request.GET.get('delivery_method', 'deliver')
    if delivery_method not in ['pickup', 'deliver']:
        delivery_method = 'deliver'

    payment_method = request.GET.get('payment_method')
    if not payment_method:
        payment_method = 'cod' if delivery_method == 'deliver' else 'over_counter'

    if delivery_method == 'pickup':
        payment_method = 'over_counter'
    elif payment_method == 'cod':
        delivery_method = 'deliver'

    DELIVERY_FEE = 20.0
    delivery_fee = DELIVERY_FEE if delivery_method == 'deliver' else 0.0

    delivery_address = (request.POST.get('delivery_address') or '').strip()

    DELIVERY_FEE = 20.0
    delivery_fee = DELIVERY_FEE if delivery_method == 'deliver' else 0.0
    grand_total = cart_total + delivery_fee

    context = {
        'cart_items': cart_items,
        'cart_total': cart_total,
        'cart_total_items': cart_total_items,
        'delivery_method': delivery_method,
        'payment_method': payment_method,
        'delivery_fee': delivery_fee,
        'delivery_fee_amount': DELIVERY_FEE,
        'grand_total': grand_total,
    }

    return render(request, 'checkout.html', context)


def cart_add(request, product_id):
    if not request.user.is_authenticated:
        return redirect('login')

    if request.user.is_superuser or request.user.is_staff:
        return redirect('admin_dashboard')

    product = get_object_or_404(Product, pk=product_id, is_active=True, stock_quantity__gt=0)

    cart = _get_cart(request)
    key = str(product_id)
    current_quantity = cart.get(key, 0)

    try:
        current_quantity = float(current_quantity)
    except (TypeError, ValueError):
        current_quantity = 0.0

    new_quantity = current_quantity + 1.0
    cart[key] = new_quantity
    _save_cart(request, cart)

    messages.success(request, f"Added {product.name} to your cart.")

    return redirect('shop_now')


def cart_update(request):
    if not request.user.is_authenticated:
        return redirect('login')

    if request.user.is_superuser or request.user.is_staff:
        return redirect('admin_dashboard')

    if request.method != 'POST':
        return redirect('cart_view')

    cart = _get_cart(request)
    updated_cart = {}

    for pid_str in cart.keys():
        field_name = f'quantity_{pid_str}'
        qty_str = request.POST.get(field_name)

        if qty_str is None:
            continue

        try:
            qty = float(qty_str)
        except (TypeError, ValueError):
            qty = cart[pid_str]

        if qty > 0:
            updated_cart[pid_str] = qty

    _save_cart(request, updated_cart)

    messages.success(request, 'Your cart has been updated.')

    return redirect('cart_view')


def cart_remove(request, product_id):
    if not request.user.is_authenticated:
        return redirect('login')

    if request.user.is_superuser or request.user.is_staff:
        return redirect('admin_dashboard')

    cart = _get_cart(request)
    key = str(product_id)

    if key in cart:
        del cart[key]
        _save_cart(request, cart)
        messages.success(request, 'Item removed from your cart.')

    return redirect('cart_view')


def cart_checkout(request):
    if not request.user.is_authenticated:
        return redirect('login')

    if request.user.is_superuser or request.user.is_staff:
        return redirect('admin_dashboard')

    if request.method != 'POST':
        return redirect('cart_view')

    cart = _get_cart(request)

    if not cart:
        messages.warning(request, 'Your cart is empty.')
        return redirect('cart_view')
 
    # Read delivery and payment choices from the checkout form
    delivery_method = request.POST.get('delivery_method', 'deliver')
    if delivery_method not in ['pickup', 'deliver']:
        delivery_method = 'deliver'

    payment_method = request.POST.get('payment_method')
    if not payment_method:
        payment_method = 'cod' if delivery_method == 'deliver' else 'over_counter'

    # Enforce business rules
    if delivery_method == 'pickup':
        payment_method = 'over_counter'
    elif payment_method == 'cod':
        delivery_method = 'deliver'

    # Compute delivery fee based on final delivery method
    DELIVERY_FEE = 20.0
    delivery_fee = DELIVERY_FEE if delivery_method == 'deliver' else 0.0

    product_ids = []
    for pid_str in cart.keys():
        try:
            product_ids.append(int(pid_str))
        except (ValueError, TypeError):
            continue

    products = Product.objects.filter(id__in=product_ids, is_active=True)
    products_map = {p.id: p for p in products}

    items_data = []  # (product, quantity_int)

    for pid_str, quantity in cart.items():
        try:
            pid = int(pid_str)
            qty = float(quantity)
        except (ValueError, TypeError):
            continue

        if qty <= 0:
            continue

        product = products_map.get(pid)
        if not product:
            continue

        # Convert kg (possibly with decimal) to an integer quantity for storage
        qty_int = int(round(qty))
        if qty_int <= 0:
            qty_int = 1

        if product.stock_quantity <= 0:
            continue

        if qty_int > product.stock_quantity:
            qty_int = product.stock_quantity

        if qty_int <= 0:
            continue

        items_data.append((product, qty_int))

    if not items_data:
        messages.error(request, 'Unable to place your order. Please check product availability or quantities.')
        _save_cart(request, {})
        return redirect('cart_view')

    with transaction.atomic():
        order = Order.objects.create(
            customer=request.user,
            status=Order.STATUS_PENDING,
            delivery_fee=delivery_fee,
        )

        for product, qty_int in items_data:
            OrderItem.objects.create(
                order=order,
                product=product,
                quantity=qty_int,
                price=product.price,
            )

            # Decrease stock
            product.stock_quantity = max(0, product.stock_quantity - qty_int)
            product.save(update_fields=['stock_quantity'])

    # Clear cart after successful checkout
    _save_cart(request, {})

    readable_delivery = 'Pick-up' if delivery_method == 'pickup' else 'Deliver'
    if payment_method == 'cod':
        readable_payment = 'Cash on delivery'
    else:
        readable_payment = 'Over the counter'

    messages.success(
        request,
        f"Your order #{order.id} has been placed successfully. "
        f"Delivery: {readable_delivery}. Payment: {readable_payment}.",
    )

    return redirect('customer_dashboard')

def admin_dashboard(request):
    if not request.user.is_authenticated:
        return redirect('login')
    
    if not (request.user.is_superuser or request.user.is_staff):
        return redirect('customer_dashboard')
    
    today = timezone.localdate()
    start_date = today - timedelta(days=6)

    # Orders placed today
    orders_today = Order.objects.filter(created_at__date=today)
    total_orders_today = orders_today.count()

    pending_orders_count = orders_today.filter(status=Order.STATUS_PENDING).count()

    # Today's sales (completed orders)
    sales_today_agg = OrderItem.objects.filter(
        order__created_at__date=today,
        order__status=Order.STATUS_COMPLETED,
    ).aggregate(
        total=Sum(F('quantity') * F('price'), output_field=DecimalField(max_digits=12, decimal_places=2))
    )
    todays_sales = sales_today_agg['total'] or 0

    # Low-stock items
    LOW_STOCK_THRESHOLD = 10
    low_stock_items_count = Product.objects.filter(
        is_active=True,
        stock_quantity__lte=LOW_STOCK_THRESHOLD,
    ).count()

    # Sales for the last 7 days (for chart)
    sales_7d_qs = (
        OrderItem.objects.filter(
            order__created_at__date__gte=start_date,
            order__created_at__date__lte=today,
            order__status=Order.STATUS_COMPLETED,
        )
        .annotate(day=TruncDate('order__created_at'))
        .values('day')
        .annotate(
            total=Sum(
                F('quantity') * F('price'),
                output_field=DecimalField(max_digits=12, decimal_places=2),
            )
        )
        .order_by('day')
    )

    sales_by_day = {entry['day']: entry['total'] for entry in sales_7d_qs}

    chart_points = []
    for i in range(7):
        day = start_date + timedelta(days=i)
        total = sales_by_day.get(day) or 0
        chart_points.append(
            {
                'date': day,
                'label': day.strftime('%a'),
                'total': float(total),
            }
        )

    max_total = max((p['total'] for p in chart_points), default=0)
    for p in chart_points:
        if max_total > 0:
            p['percent'] = int((p['total'] / max_total) * 100)
        else:
            p['percent'] = 0

    # Recent 5 orders with totals
    recent_orders = (
        Order.objects.select_related('customer')
        .annotate(
            total_amount=Sum(
                F('items__quantity') * F('items__price'),
                output_field=DecimalField(max_digits=12, decimal_places=2),
            )
        )
        .order_by('-created_at')[:5]
    )

    context = {
        'todays_sales': todays_sales,
        'total_orders_today': total_orders_today,
        'pending_orders_count': pending_orders_count,
        'low_stock_items_count': low_stock_items_count,
        'chart_points': chart_points,
        'recent_orders': recent_orders,
        'low_stock_threshold': LOW_STOCK_THRESHOLD,
    }

    return render(request, 'admin_dashboard.html', context)

def admin_products(request):
    if not request.user.is_authenticated:
        return redirect('login')
    
    if not (request.user.is_superuser or request.user.is_staff):
        return redirect('customer_dashboard')
    
    query = request.GET.get('q', '').strip()
    status_filter = request.GET.get('status', 'all')
    category_filter = request.GET.get('category', 'all')

    products = Product.objects.all().order_by('category', 'name')

    if query:
        products = products.filter(name__icontains=query)

    # Category filter: all products, fruits only, vegetables only
    if category_filter == 'fruits':
        products = products.filter(category__iexact='Fruits')
    elif category_filter == 'vegetables':
        products = products.filter(category__iexact='Vegetables')

    LOW_STOCK_THRESHOLD = 10

    if status_filter == 'available':
        products = products.filter(is_active=True, stock_quantity__gt=0)
    elif status_filter == 'low_stock':
        products = products.filter(is_active=True, stock_quantity__gt=0, stock_quantity__lte=LOW_STOCK_THRESHOLD)
    elif status_filter == 'unavailable':
        products = products.filter(is_active=False) | products.filter(stock_quantity__lte=0)

    paginator = Paginator(products, 9)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'products': page_obj,
        'page_obj': page_obj,
        'paginator': paginator,
        'query': query,
        'status_filter': status_filter,
        'category_filter': category_filter,
        'low_stock_threshold': LOW_STOCK_THRESHOLD,
    }

    return render(request, 'products.html', context)


def admin_product_add(request):
    if not request.user.is_authenticated:
        return redirect('login')

    if not (request.user.is_superuser or request.user.is_staff):
        return redirect('customer_dashboard')

    if request.method == 'POST':
        form = ProductForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Product added successfully.')
            return redirect('admin_products')
    else:
        form = ProductForm()

    return render(request, 'product_form.html', {
        'form': form,
        'form_title': 'Add product',
        'submit_label': 'Create product',
    })


def admin_product_edit(request, pk):
    if not request.user.is_authenticated:
        return redirect('login')

    if not (request.user.is_superuser or request.user.is_staff):
        return redirect('customer_dashboard')

    product = get_object_or_404(Product, pk=pk)

    if request.method == 'POST':
        form = ProductForm(request.POST, instance=product)
        if form.is_valid():
            form.save()
            messages.success(request, 'Product updated successfully.')
            return redirect('admin_products')
    else:
        form = ProductForm(instance=product)

    return render(request, 'product_form.html', {
        'form': form,
        'form_title': f'Edit product: {product.name}',
        'submit_label': 'Save changes',
    })


def admin_product_stock(request, pk):
    if not request.user.is_authenticated:
        return redirect('login')

    if not (request.user.is_superuser or request.user.is_staff):
        return redirect('customer_dashboard')

    product = get_object_or_404(Product, pk=pk)

    if request.method == 'POST':
        form = StockUpdateForm(request.POST, instance=product)
        if form.is_valid():
            form.save()
            messages.success(request, 'Stock updated successfully.')
            return redirect('admin_products')
    else:
        form = StockUpdateForm(instance=product)

    return render(request, 'product_stock_form.html', {
        'form': form,
        'product': product,
    })


def admin_product_toggle(request, pk):
    if not request.user.is_authenticated:
        return redirect('login')

    if not (request.user.is_superuser or request.user.is_staff):
        return redirect('customer_dashboard')

    if request.method != 'POST':
        return redirect('admin_products')

    product = get_object_or_404(Product, pk=pk)
    product.is_active = not product.is_active
    product.save(update_fields=['is_active'])
    messages.success(request, 'Product availability updated.')
    return redirect('admin_products')


def admin_product_delete(request, pk):
    if not request.user.is_authenticated:
        return redirect('login')

    if not (request.user.is_superuser or request.user.is_staff):
        return redirect('customer_dashboard')

    product = get_object_or_404(Product, pk=pk)

    if request.method == 'POST':
        product.delete()
        messages.success(request, 'Product deleted successfully.')
        return redirect('admin_products')

    return render(request, 'product_delete_confirm.html', {'product': product})

def admin_orders(request):
    if not request.user.is_authenticated:
        return redirect('login')
    
    if not (request.user.is_superuser or request.user.is_staff):
        return redirect('customer_dashboard')
    
    status_filter = request.GET.get('status', 'all')

    orders = (
        Order.objects.select_related('customer')
        .annotate(
            items_count=Count('items', distinct=True),
            total_amount=Sum(
                F('items__quantity') * F('items__price'),
                output_field=DecimalField(max_digits=12, decimal_places=2),
            ),
        )
        .order_by('-created_at')
    )

    if status_filter != 'all':
        orders = orders.filter(status=status_filter)

    context = {
        'orders': orders,
        'status_filter': status_filter,
    }

    return render(request, 'orders.html', context)


def admin_order_update_status(request, order_id):
    if not request.user.is_authenticated:
        return redirect('login')

    if not (request.user.is_superuser or request.user.is_staff):
        return redirect('customer_dashboard')

    if request.method != 'POST':
        return redirect('admin_orders')

    order = get_object_or_404(Order, pk=order_id)

    new_status = request.POST.get('status')
    valid_statuses = {
        Order.STATUS_PENDING,
        Order.STATUS_PREPARING,
        Order.STATUS_OUT_FOR_DELIVERY,
        Order.STATUS_COMPLETED,
        Order.STATUS_CANCELLED,
    }

    if new_status in valid_statuses:
        order.status = new_status
        order.save(update_fields=['status', 'updated_at'])
        messages.success(request, f'Order #{order.id} status updated to {order.get_status_display()}')
    else:
        messages.error(request, 'Invalid status selected.')

    return redirect('admin_orders')

def admin_customers(request):
    if not request.user.is_authenticated:
        return redirect('login')
    
    if not (request.user.is_superuser or request.user.is_staff):
        return redirect('customer_dashboard')
    
    customers = (
        User.objects.filter(is_staff=False, is_superuser=False)
        .annotate(
            total_orders=Count('orders', distinct=True),
            total_spent=Sum(
                F('orders__items__quantity') * F('orders__items__price'),
                output_field=DecimalField(max_digits=12, decimal_places=2),
            ),
            last_order_date=Max('orders__created_at'),
        )
        .order_by('-last_order_date', 'first_name', 'last_name')
    )

    context = {
        'customers': customers,
    }

    return render(request, 'view_customers.html', context)

def admin_reports(request):
    if not request.user.is_authenticated:
        return redirect('login')
    
    if not (request.user.is_superuser or request.user.is_staff):
        return redirect('customer_dashboard')
    
    today = timezone.localdate()
    start_7d = today - timedelta(days=6)
    month_start = today.replace(day=1)

    base_items = OrderItem.objects.filter(order__status=Order.STATUS_COMPLETED)

    # Optional custom date range for product-level stats
    start_param = request.GET.get('start')
    end_param = request.GET.get('end')

    filter_start = month_start
    filter_end = today
    period_label = 'This month'

    if start_param and end_param:
        filter_start = start_param
        filter_end = end_param
        period_label = f"{start_param} to {end_param}"

    def _sales_total(qs):
        agg = qs.aggregate(
            total=Sum(
                F('quantity') * F('price'),
                output_field=DecimalField(max_digits=12, decimal_places=2),
            )
        )
        return agg['total'] or 0

    # Daily, weekly, monthly sales
    daily_sales = _sales_total(
        base_items.filter(order__created_at__date=today)
    )

    weekly_sales = _sales_total(
        base_items.filter(
            order__created_at__date__gte=start_7d,
            order__created_at__date__lte=today,
        )
    )

    monthly_sales = _sales_total(
        base_items.filter(
            order__created_at__date__gte=month_start,
            order__created_at__date__lte=today,
        )
    )

    # Top-selling products for the selected period (by quantity)
    top_products = (
        base_items.filter(
            order__created_at__date__gte=filter_start,
            order__created_at__date__lte=filter_end,
        )
        .values('product_id')
        .annotate(
            product_name=Max('product__name'),
            product_category=Max('product__category'),
            total_quantity=Sum('quantity'),
            total_revenue=Sum(
                F('quantity') * F('price'),
                output_field=DecimalField(max_digits=12, decimal_places=2),
            ),
        )
        .order_by('-total_quantity')[:5]
    )

    context = {
        'daily_sales': daily_sales,
        'weekly_sales': weekly_sales,
        'monthly_sales': monthly_sales,
        'top_products': top_products,
        'report_start': start_param or '',
        'report_end': end_param or '',
        'period_label': period_label,
    }

    return render(request, 'report.html', context)
