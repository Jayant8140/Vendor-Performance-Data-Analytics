import sqlite3
import pandas as pd
import logging
from ingestion import ingest_db
from sqlalchemy import create_engine, text


logging.basicConfig(
    filename="logs1/get_vendor_summary.log",
    level=logging.DEBUG,
    format="%(asctime)s - %(levelname)s - %(message)s",
    filemode="a"
)

def create_vendor_summary(conn):
    ''' This function will merge the different tables to get the overall vendor summary and adding new columns in the resulting data '''
    vendor_sales_summary=pd.read_sql_query("""with FreightSummary as (
        select 
        VendorNumber,
        sum(Freight) as FreightCost
        from vendor_invoice
        group by VendorNumber
        ),
        
        PurchaseSummary as (
        select 
        p.VendorNumber,
        p.VendorName,
        p.Brand,
        p.Description,
        p.PurchasePrice,
        pp.price as ActualPrice,
        pp.Volume,
        sum(p.Quantity) as TotalPurchaseQuantity,
        sum(p.Dollars) as TotalPurchaseDollars
        from purchases as p
        join purchase_prices pp 
        on p.Brand=pp.Brand
        where p.PurchasePrice>0
        group by p.VendorNumber,p.VendorName,p.Brand,p.Description,p.PurchasePrice,pp.Price,pp.Volume
        ),
        
        SalesSummary as (
        select 
        VendorNo,
        Brand,
        sum(SalesQuantity) as TotalSalesQuantity,
        sum(SalesDollars) as TotalSalesDollars,
        sum(SalesPrice) as TotalSalesPrice,
        sum(ExciseTax) as TotalExciseTax
        from sales
        group by VendorNo,Brand
        )
        
        select 
        ps.VendorNumber,
        ps.VendorName,
        ps.Brand,
        ps.Description,
        ps.PurchasePrice,
        ps.ActualPrice,
        ps.Volume,
        ps.TotalPurchaseQuantity,
        ps.TotalPurchaseDollars,
        ss.TotalSalesQuantity,
        ss.TotalSalesDollars,
        ss.TotalSalesPrice,
        ss.TotalExciseTax,
        fs.FreightCost
        from PurchaseSummary as ps
        left join SalesSummary as ss
        on ps.VendorNumber=ss.VendorNo
        and ps.Brand=ss.Brand
        left join FreightSummary as fs 
        on ps.VendorNumber=fs.VendorNumber
        order by ps.TotalPurchaseDollars desc
        """,conn)
    return vendor_sales_summary

def clean_data(df):
    #Changing datatype to Float
    df['Volume']=df['Volume'].astype('float64')


    #filling missing Value
    df.fillna(0,inplace=True)

    #Removing space from categorical columns
    df['VendorName']=df['VendorName'].str.strip()
    df['Description']=df['Description'].str.strip()


    #Creating new columns for better analysis
    df['GrossProfit']=df['TotalSalesDollars']-df['TotalPurchaseDollars']
    df['ProfitMargin']=df['GrossProfit']/df['TotalSalesDollars']*100
    df['StockTurnover']= df['TotalSalesQuantity']/df['TotalPurchaseQuantity']
    df['SalesToPurchaseRatio']=df['TotalSalesDollars']/df['TotalPurchaseDollars']
    
    
    return df


if __name__ == '__main__':
    # ✅ Create engine
    engine = create_engine("sqlite:///inventory.db")

    # ✅ Create indexes
    with engine.connect() as conn:
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_purchase_vendor_brand ON purchases(VendorNumber, Brand);"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_sales_vendor_brand ON sales(VendorNo, Brand);"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_invoice_vendor ON vendor_invoice(VendorNumber);"))
        conn.commit()

    logging.info('Creating vendor summary table......')
    summary_df = create_vendor_summary(engine)
    logging.info("\n" + summary_df.head().to_string())

    logging.info('Cleaning Data......')
    clean_df = clean_data(summary_df)
    logging.info("\n" + clean_df.head().to_string())

    logging.info('Ingesting Data..........')
    ingest_db(clean_df, 'vendor_sales_summary', engine)
    logging.info('Completed')

    
















